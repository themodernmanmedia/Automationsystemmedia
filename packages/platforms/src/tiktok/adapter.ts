/**
 * TikTok adapter — Content Posting API (Direct Post) + Display API.
 *
 * Two things make TikTok different from Meta and both are enforced here:
 *
 * 1. creator_info/query MUST be called before every post. It returns the
 *    privacy levels the creator permits, whether comment/duet/stitch are
 *    allowed, and the creator's own max video duration. Posting without
 *    honoring these is a policy violation and gets rejected anyway.
 *
 * 2. Until the API client passes TikTok's audit, EVERY post is forced to
 *    SELF_ONLY (private) regardless of the requested privacy level. We surface
 *    that on the result as `restrictedVisibility` so the dashboard can tell the
 *    truth rather than reporting a public post that nobody can see.
 */
import { CapabilityNotSupportedError, PlatformApiError, ValidationError, sleep } from '@mmos/core';
import type {
  AccountAnalytics,
  AdapterContext,
  CreatePostInput,
  NormalizedAnalytics,
  OAuthTokens,
  PlatformAccount,
  PlatformAdapter,
  PlatformCapabilities,
  PostStatus,
  PublishResult,
  RateLimitStatus,
  ValidationIssue,
} from '../types.js';
import { TIKTOK_CAPABILITIES } from '../capabilities.js';
import { buildUrl, request } from '../http.js';
import { validateAgainstCapabilities } from '../validation.js';
import { readFile, stat } from 'node:fs/promises';

export interface TikTokAdapterConfig {
  clientKey: string;
  clientSecret: string;
  redirectUri: string;
  baseUrl?: string;
  authBaseUrl?: string;
}

export interface CreatorInfo {
  nickname: string;
  avatarUrl?: string;
  privacyLevelOptions: string[];
  commentDisabled: boolean;
  duetDisabled: boolean;
  stitchDisabled: boolean;
  maxVideoPostDurationSec: number;
}

interface TikTokEnvelope<T> {
  data?: T;
  error?: { code?: string; message?: string; log_id?: string };
}

/** TikTok returns error.code = "ok" on success; anything else is a failure. */
function unwrap<T>(body: TikTokEnvelope<T>, operation: string): T {
  const code = body.error?.code;
  if (code && code !== 'ok') {
    throw new PlatformApiError('TIKTOK', `${operation} failed: ${body.error?.message ?? code}`, {
      platformCode: code,
      // spam_risk / rate limits are worth retrying; everything else is not.
      retryable: code === 'rate_limit_exceeded' || code === 'internal_error',
      context: { logId: body.error?.log_id },
    });
  }
  if (!body.data) {
    throw new PlatformApiError('TIKTOK', `${operation} returned no data`, { retryable: false });
  }
  return body.data;
}

export class TikTokAdapter implements PlatformAdapter {
  readonly platform = 'TIKTOK' as const;
  readonly #config: TikTokAdapterConfig;
  readonly #base: string;
  readonly #authBase: string;

  constructor(config: TikTokAdapterConfig) {
    this.#config = config;
    this.#base = config.baseUrl ?? 'https://open.tiktokapis.com';
    this.#authBase = config.authBaseUrl ?? 'https://www.tiktok.com';
  }

  getPublishingCapabilities(): PlatformCapabilities {
    return TIKTOK_CAPABILITIES;
  }

  /* -------------------------------- OAuth -------------------------------- */

  getAuthorizationUrl(state: string, scopes?: string[]): string {
    return buildUrl(this.#authBase, 'v2/auth/authorize/', {
      client_key: this.#config.clientKey,
      scope: (scopes ?? TIKTOK_CAPABILITIES.requiredScopes).join(','),
      response_type: 'code',
      redirect_uri: this.#config.redirectUri,
      state,
    });
  }

  async exchangeCodeForTokens(code: string): Promise<OAuthTokens> {
    const res = await request<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
      refresh_expires_in: number;
      scope: string;
      open_id: string;
    }>(
      {
        method: 'POST',
        url: buildUrl(this.#base, 'v2/oauth/token/'),
        form: {
          client_key: this.#config.clientKey,
          client_secret: this.#config.clientSecret,
          code,
          grant_type: 'authorization_code',
          redirect_uri: this.#config.redirectUri,
        },
      },
      'TIKTOK',
    );
    return this.#toTokens(res.body);
  }

  async refreshToken(refreshToken: string): Promise<OAuthTokens> {
    const res = await request<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
      refresh_expires_in: number;
      scope: string;
    }>(
      {
        method: 'POST',
        url: buildUrl(this.#base, 'v2/oauth/token/'),
        form: {
          client_key: this.#config.clientKey,
          client_secret: this.#config.clientSecret,
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
        },
      },
      'TIKTOK',
    );
    return this.#toTokens(res.body);
  }

  #toTokens(b: {
    access_token: string;
    refresh_token: string;
    expires_in: number;
    refresh_expires_in: number;
    scope: string;
  }): OAuthTokens {
    return {
      accessToken: b.access_token,
      refreshToken: b.refresh_token,
      // Access tokens last only ~24h, so the refresh worker must run reliably.
      expiresAt: new Date(Date.now() + b.expires_in * 1000),
      refreshExpiresAt: new Date(Date.now() + b.refresh_expires_in * 1000),
      scopes: b.scope ? b.scope.split(',') : [],
      raw: b,
    };
  }

  /* ------------------------------- account ------------------------------- */

  async getAccount(ctx: AdapterContext): Promise<PlatformAccount> {
    const res = await request<
      TikTokEnvelope<{
        user: {
          open_id: string;
          display_name?: string;
          username?: string;
          avatar_url?: string;
          follower_count?: number;
        };
      }>
    >(
      {
        method: 'GET',
        url: buildUrl(this.#base, 'v2/user/info/', {
          fields: 'open_id,display_name,username,avatar_url,follower_count',
        }),
        headers: { Authorization: `Bearer ${ctx.accessToken}` },
      },
      'TIKTOK',
    );
    const user = unwrap(res.body, 'user/info').user;
    return {
      platformAccountId: user.open_id,
      username: user.username ?? user.display_name ?? user.open_id,
      ...(user.display_name ? { displayName: user.display_name } : {}),
      ...(user.avatar_url ? { profileImageUrl: user.avatar_url } : {}),
      ...(user.follower_count !== undefined ? { followerCount: user.follower_count } : {}),
      accountType: 'CREATOR',
      raw: user,
    };
  }

  /**
   * Mandatory pre-publish call. Everything it returns is a constraint we must
   * honor, not advice.
   */
  async getCreatorInfo(ctx: AdapterContext): Promise<CreatorInfo> {
    const res = await request<
      TikTokEnvelope<{
        creator_nickname: string;
        creator_avatar_url?: string;
        privacy_level_options: string[];
        comment_disabled: boolean;
        duet_disabled: boolean;
        stitch_disabled: boolean;
        max_video_post_duration_sec: number;
      }>
    >(
      {
        method: 'POST',
        url: buildUrl(this.#base, 'v2/post/publish/creator_info/query/'),
        headers: { Authorization: `Bearer ${ctx.accessToken}` },
        body: {},
      },
      'TIKTOK',
    );
    const d = unwrap(res.body, 'creator_info/query');
    return {
      nickname: d.creator_nickname,
      ...(d.creator_avatar_url ? { avatarUrl: d.creator_avatar_url } : {}),
      privacyLevelOptions: d.privacy_level_options ?? [],
      commentDisabled: d.comment_disabled,
      duetDisabled: d.duet_disabled,
      stitchDisabled: d.stitch_disabled,
      maxVideoPostDurationSec: d.max_video_post_duration_sec,
    };
  }

  /** TikTok exposes no publish-quota endpoint; creator_info doubles as a liveness check. */
  async checkRateLimit(ctx: AdapterContext): Promise<RateLimitStatus> {
    try {
      await this.getCreatorInfo(ctx);
      return { canPublish: true };
    } catch (err) {
      return { canPublish: false, reason: (err as Error).message };
    }
  }

  /* ------------------------------ publishing ----------------------------- */

  validate(input: CreatePostInput): ValidationIssue[] {
    return validateAgainstCapabilities(input, TIKTOK_CAPABILITIES);
  }

  async createPost(ctx: AdapterContext, input: CreatePostInput): Promise<PublishResult> {
    const issues = this.validate(input);
    const errors = issues.filter((i) => i.severity === 'ERROR');
    if (errors.length > 0) {
      throw new ValidationError(`TikTok validation failed: ${errors.map((e) => e.message).join('; ')}`, {
        issues: errors,
      });
    }

    if (input.scheduledAt && input.scheduledAt.getTime() > Date.now() + 60_000) {
      throw new CapabilityNotSupportedError(
        'TikTok',
        'native scheduling',
        'The Content Posting API has no scheduling parameter. Route this through the system scheduler.',
      );
    }

    const creator = await this.getCreatorInfo(ctx);

    // Honor the creator's own settings. Requesting an option they have turned
    // off is both a policy violation and a guaranteed rejection.
    const requested = input.privacyLevel ?? creator.privacyLevelOptions[0];
    if (!requested || !creator.privacyLevelOptions.includes(requested)) {
      throw new ValidationError(
        `Privacy level "${requested}" is not permitted for this creator. Allowed: ${creator.privacyLevelOptions.join(', ') || '(none returned)'}.`,
      );
    }

    const video = input.media.find((m) => m.kind === 'VIDEO');
    if (video?.durationSec && video.durationSec > creator.maxVideoPostDurationSec) {
      throw new ValidationError(
        `Video is ${video.durationSec}s but this creator's maximum is ${creator.maxVideoPostDurationSec}s.`,
      );
    }

    const result = video
      ? await this.#postVideo(ctx, input, video.localPath ?? video.url, requested, creator)
      : await this.#postPhotos(ctx, input, requested);

    // Unaudited clients get SELF_ONLY regardless of what was requested. Report it.
    const restricted = ctx.isAudited !== true;
    return {
      ...result,
      restrictedVisibility: restricted,
      ...(restricted
        ? {
            visibilityNote:
              'This API client has not passed TikTok audit, so the post is restricted to SELF_ONLY (private) visibility regardless of the requested privacy level.',
          }
        : {}),
    };
  }

  async #postVideo(
    ctx: AdapterContext,
    input: CreatePostInput,
    source: string,
    privacyLevel: string,
    creator: CreatorInfo,
  ): Promise<PublishResult> {
    const isLocal = !source.startsWith('http');
    const postInfo: Record<string, unknown> = {
      title: input.caption.slice(0, TIKTOK_CAPABILITIES.captionMaxLength),
      privacy_level: privacyLevel,
      disable_comment: input.disableComment ?? creator.commentDisabled,
      disable_duet: input.disableDuet ?? creator.duetDisabled,
      disable_stitch: input.disableStitch ?? creator.stitchDisabled,
    };

    let sourceInfo: Record<string, unknown>;
    let fileBuffer: Buffer | undefined;

    if (isLocal) {
      const fileStat = await stat(source);
      fileBuffer = await readFile(source);
      sourceInfo = {
        source: 'FILE_UPLOAD',
        video_size: fileStat.size,
        // Single-chunk upload. Files beyond TikTok's chunk ceiling would need
        // splitting; the renderer produces short-form vertical video well under it.
        chunk_size: fileStat.size,
        total_chunk_count: 1,
      };
    } else {
      sourceInfo = { source: 'PULL_FROM_URL', video_url: source };
    }

    const init = await request<TikTokEnvelope<{ publish_id: string; upload_url?: string }>>(
      {
        method: 'POST',
        url: buildUrl(this.#base, 'v2/post/publish/video/init/'),
        headers: { Authorization: `Bearer ${ctx.accessToken}` },
        body: { post_info: postInfo, source_info: sourceInfo },
      },
      'TIKTOK',
    );
    const { publish_id, upload_url } = unwrap(init.body, 'video/init');

    if (isLocal && upload_url && fileBuffer) {
      const size = fileBuffer.byteLength;
      const res = await fetch(upload_url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'video/mp4',
          'Content-Length': String(size),
          'Content-Range': `bytes 0-${size - 1}/${size}`,
        },
        body: new Uint8Array(fileBuffer),
      });
      if (!res.ok) {
        throw new PlatformApiError('TIKTOK', `Video upload failed with HTTP ${res.status}`, {
          retryable: res.status >= 500,
          context: { publishId: publish_id },
        });
      }
    }

    const status = await this.#awaitPublishComplete(ctx, publish_id);
    return {
      platformPostId: status.platformPostId ?? publish_id,
      publishedAt: new Date(),
      scheduledByPlatform: false,
      raw: status.raw,
    };
  }

  async #postPhotos(
    ctx: AdapterContext,
    input: CreatePostInput,
    privacyLevel: string,
  ): Promise<PublishResult> {
    const urls = input.media.filter((m) => m.kind === 'IMAGE').map((m) => m.url);
    if (urls.length === 0) throw new ValidationError('No images supplied for a TikTok photo post');

    const init = await request<TikTokEnvelope<{ publish_id: string }>>(
      {
        method: 'POST',
        url: buildUrl(this.#base, 'v2/post/publish/content/init/'),
        headers: { Authorization: `Bearer ${ctx.accessToken}` },
        body: {
          post_info: {
            title: input.caption.slice(0, 90),
            description: input.caption.slice(0, TIKTOK_CAPABILITIES.captionMaxLength),
            privacy_level: privacyLevel,
            disable_comment: input.disableComment ?? false,
          },
          source_info: { source: 'PULL_FROM_URL', photo_cover_index: 0, photo_images: urls },
          post_mode: 'DIRECT_POST',
          media_type: 'PHOTO',
        },
      },
      'TIKTOK',
    );
    const { publish_id } = unwrap(init.body, 'content/init');
    const status = await this.#awaitPublishComplete(ctx, publish_id);
    return {
      platformPostId: status.platformPostId ?? publish_id,
      publishedAt: new Date(),
      scheduledByPlatform: false,
      raw: status.raw,
    };
  }

  async #awaitPublishComplete(
    ctx: AdapterContext,
    publishId: string,
    { timeoutMs = 5 * 60_000, intervalMs = 5_000 }: { timeoutMs?: number; intervalMs?: number } = {},
  ): Promise<PostStatus> {
    const deadline = Date.now() + timeoutMs;
    let last: PostStatus | undefined;
    while (Date.now() < deadline) {
      last = await this.getPostStatus(ctx, publishId);
      if (last.state === 'PUBLISHED') return last;
      if (last.state === 'FAILED') {
        throw new PlatformApiError('TIKTOK', `Publish failed: ${last.error ?? 'unknown reason'}`, {
          retryable: false,
          context: { publishId },
        });
      }
      await sleep(intervalMs);
    }
    throw new PlatformApiError('TIKTOK', `Publish did not complete within ${timeoutMs / 1000}s`, {
      retryable: true,
      context: { publishId, lastState: last?.state },
    });
  }

  async getPostStatus(ctx: AdapterContext, publishId: string): Promise<PostStatus> {
    const res = await request<
      TikTokEnvelope<{ status: string; publicaly_available_post_id?: string[]; fail_reason?: string }>
    >(
      {
        method: 'POST',
        url: buildUrl(this.#base, 'v2/post/publish/status/fetch/'),
        headers: { Authorization: `Bearer ${ctx.accessToken}` },
        body: { publish_id: publishId },
      },
      'TIKTOK',
    );
    const d = unwrap(res.body, 'status/fetch');
    const state =
      d.status === 'PUBLISH_COMPLETE'
        ? 'PUBLISHED'
        : d.status === 'FAILED'
          ? 'FAILED'
          : 'PROCESSING';
    return {
      state,
      // Note the spelling: TikTok's field is misspelled in their API, not here.
      ...(d.publicaly_available_post_id?.[0] ? { platformPostId: d.publicaly_available_post_id[0] } : {}),
      ...(d.fail_reason ? { error: d.fail_reason } : {}),
      raw: d,
    };
  }

  /* ------------------------------ analytics ------------------------------ */

  async getAnalytics(ctx: AdapterContext, platformPostId: string): Promise<NormalizedAnalytics> {
    const res = await request<
      TikTokEnvelope<{
        videos: Array<{
          id: string;
          view_count?: number;
          like_count?: number;
          comment_count?: number;
          share_count?: number;
        }>;
      }>
    >(
      {
        method: 'POST',
        url: buildUrl(this.#base, 'v2/video/query/', {
          fields: 'id,view_count,like_count,comment_count,share_count',
        }),
        headers: { Authorization: `Bearer ${ctx.accessToken}` },
        body: { filters: { video_ids: [platformPostId] } },
      },
      'TIKTOK',
    );
    const video = unwrap(res.body, 'video/query').videos?.[0];
    const views = video?.view_count ?? null;
    const likes = video?.like_count ?? null;
    const comments = video?.comment_count ?? null;
    const shares = video?.share_count ?? null;
    const interactions = [likes, comments, shares].filter((v): v is number => v !== null);

    return {
      platformPostId,
      collectedAt: new Date(),
      views,
      reach: null,
      impressions: null,
      likes,
      comments,
      shares,
      saves: null,
      watchTimeSec: null,
      avgWatchTimeSec: null,
      retentionRate: null,
      profileVisits: null,
      followsGained: null,
      clicks: null,
      engagementRate:
        views && views > 0 && interactions.length > 0
          ? interactions.reduce((a, b) => a + b, 0) / views
          : null,
      // The Display API is far thinner than TikTok's own creator dashboard.
      unavailableMetrics: ['reach', 'impressions', 'saves', 'watchTime', 'retention', 'profileVisits', 'follows'],
      raw: video,
    };
  }

  async getAccountAnalytics(ctx: AdapterContext): Promise<AccountAnalytics> {
    const account = await this.getAccount(ctx);
    return {
      collectedAt: new Date(),
      followerCount: account.followerCount ?? null,
      reach: null,
      views: null,
      unavailableMetrics: ['reach', 'views', 'impressions', 'profileVisits'],
      raw: account.raw,
    };
  }

  /* --------------------------- unsupported ops --------------------------- */

  async deletePost(): Promise<void> {
    throw new CapabilityNotSupportedError(
      'TikTok',
      'delete post',
      'The Content Posting API has no delete endpoint. Remove the post in the TikTok app.',
    );
  }

  async updatePost(): Promise<void> {
    throw new CapabilityNotSupportedError(
      'TikTok',
      'edit post',
      'Published TikTok posts cannot be edited through the API.',
    );
  }
}
