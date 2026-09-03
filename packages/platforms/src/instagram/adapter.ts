/**
 * Instagram adapter — Instagram Graph API (Content Publishing).
 *
 * Publishing is a container flow, not a single call:
 *   POST /{ig-user-id}/media          -> creation_id
 *   (video: poll GET /{creation_id}?fields=status_code until FINISHED)
 *   POST /{ig-user-id}/media_publish  -> live media id
 *
 * Carousels add a layer: one child container per item, then a parent container
 * listing the children, then publish the parent.
 *
 * Meta FETCHES the media from a public URL we supply. We never upload bytes.
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
import { INSTAGRAM_CAPABILITIES } from '../capabilities.js';
import { buildUrl, request } from '../http.js';
import { validateAgainstCapabilities } from '../validation.js';
import { IG_MEDIA_METRICS, IG_ACCOUNT_METRICS, IG_DEPRECATED_METRICS } from './metrics.js';

export interface InstagramAdapterConfig {
  appId: string;
  appSecret: string;
  redirectUri: string;
  graphVersion: string;
  /** Override for tests; nock intercepts this host. */
  baseUrl?: string;
}

interface ContainerResponse { id: string }
interface PublishResponse { id: string }
interface ContainerStatusResponse { status_code?: string; status?: string; id: string }

const TERMINAL_CONTAINER_ERRORS = new Set(['ERROR', 'EXPIRED']);

export class InstagramAdapter implements PlatformAdapter {
  readonly platform = 'INSTAGRAM' as const;
  readonly #config: InstagramAdapterConfig;
  readonly #base: string;

  constructor(config: InstagramAdapterConfig) {
    this.#config = config;
    this.#base = `${config.baseUrl ?? 'https://graph.facebook.com'}/${config.graphVersion}/`;
  }

  getPublishingCapabilities(): PlatformCapabilities {
    return INSTAGRAM_CAPABILITIES;
  }

  /* -------------------------------- OAuth -------------------------------- */

  getAuthorizationUrl(state: string, scopes?: string[]): string {
    return buildUrl('https://www.facebook.com', `${this.#config.graphVersion}/dialog/oauth`, {
      client_id: this.#config.appId,
      redirect_uri: this.#config.redirectUri,
      state,
      response_type: 'code',
      scope: (scopes ?? INSTAGRAM_CAPABILITIES.requiredScopes).join(','),
    });
  }

  async exchangeCodeForTokens(code: string): Promise<OAuthTokens> {
    const short = await request<{ access_token: string; expires_in?: number }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, 'oauth/access_token', {
          client_id: this.#config.appId,
          client_secret: this.#config.appSecret,
          redirect_uri: this.#config.redirectUri,
          code,
        }),
      },
      'INSTAGRAM',
    );

    // Short-lived tokens last ~1 hour, which is useless for a scheduler. Always
    // immediately exchange for the 60-day long-lived token.
    return this.#exchangeForLongLived(short.body.access_token);
  }

  async #exchangeForLongLived(accessToken: string): Promise<OAuthTokens> {
    const res = await request<{ access_token: string; expires_in?: number }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, 'oauth/access_token', {
          grant_type: 'fb_exchange_token',
          client_id: this.#config.appId,
          client_secret: this.#config.appSecret,
          fb_exchange_token: accessToken,
        }),
      },
      'INSTAGRAM',
    );
    const expiresIn = res.body.expires_in ?? 60 * 24 * 3600;
    return {
      accessToken: res.body.access_token,
      refreshToken: null,
      expiresAt: new Date(Date.now() + expiresIn * 1000),
      scopes: [...INSTAGRAM_CAPABILITIES.requiredScopes],
      raw: res.body,
    };
  }

  /** Meta has no refresh grant; a long-lived token is re-exchanged for a new one. */
  async refreshToken(currentToken: string): Promise<OAuthTokens> {
    return this.#exchangeForLongLived(currentToken);
  }

  /* ------------------------------- account ------------------------------- */

  async getAccount(ctx: AdapterContext): Promise<PlatformAccount> {
    const res = await request<{
      id: string;
      username: string;
      name?: string;
      profile_picture_url?: string;
      followers_count?: number;
      account_type?: string;
    }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, ctx.platformAccountId, {
          fields: 'id,username,name,profile_picture_url,followers_count',
          access_token: ctx.accessToken,
        }),
      },
      'INSTAGRAM',
    );
    const b = res.body;
    return {
      platformAccountId: b.id,
      username: b.username,
      ...(b.name ? { displayName: b.name } : {}),
      ...(b.profile_picture_url ? { profileImageUrl: b.profile_picture_url } : {}),
      ...(b.followers_count !== undefined ? { followerCount: b.followers_count } : {}),
      accountType: b.account_type ?? 'BUSINESS',
      raw: b,
    };
  }

  /**
   * Checks the rolling 100-post publishing window BEFORE publishing. Cheap
   * insurance: a rejected publish still costs an API call and a retry cycle.
   */
  async checkRateLimit(ctx: AdapterContext): Promise<RateLimitStatus> {
    const res = await request<{ data?: Array<{ quota_usage?: number; config?: { quota_total?: number } }> }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, `${ctx.platformAccountId}/content_publishing_limit`, {
          fields: 'config,quota_usage',
          access_token: ctx.accessToken,
        }),
      },
      'INSTAGRAM',
    );
    const entry = res.body.data?.[0];
    const used = entry?.quota_usage ?? 0;
    const limit = entry?.config?.quota_total ?? INSTAGRAM_CAPABILITIES.postsPer24h ?? 100;
    const remaining = Math.max(0, limit - used);
    return {
      used,
      limit,
      remaining,
      canPublish: remaining > 0,
      ...(remaining > 0
        ? {}
        : { reason: `Instagram publishing limit reached (${used}/${limit} in the rolling 24h window).` }),
    };
  }

  /* ------------------------------ publishing ----------------------------- */

  validate(input: CreatePostInput): ValidationIssue[] {
    return validateAgainstCapabilities(input, INSTAGRAM_CAPABILITIES);
  }

  async createPost(ctx: AdapterContext, input: CreatePostInput): Promise<PublishResult> {
    const issues = this.validate(input);
    const errors = issues.filter((i) => i.severity === 'ERROR');
    if (errors.length > 0) {
      throw new ValidationError(`Instagram validation failed: ${errors.map((e) => e.message).join('; ')}`, {
        issues: errors,
      });
    }

    // Instagram cannot schedule. A caller that reaches here with a future time
    // has bypassed the scheduler; fail loudly rather than publishing early.
    if (input.scheduledAt && input.scheduledAt.getTime() > Date.now() + 60_000) {
      throw new CapabilityNotSupportedError(
        'Instagram',
        'native scheduling',
        'The Graph API accepts no scheduled_publish_time. Route this through the system scheduler, which publishes at the target time.',
      );
    }

    const limit = await this.checkRateLimit(ctx);
    if (!limit.canPublish) {
      throw new PlatformApiError('INSTAGRAM', limit.reason ?? 'Publishing limit reached', {
        retryable: true,
        retryAfterMs: 60 * 60 * 1000,
      });
    }

    const containerId =
      input.kind === 'CAROUSEL'
        ? await this.#createCarouselContainer(ctx, input)
        : await this.#createSingleContainer(ctx, input);

    // Video containers are transcoded asynchronously and carousel parents are
    // assembled asynchronously; publishing either before it reports FINISHED
    // fails. A single image container is ready immediately.
    const needsPolling =
      input.kind === 'CAROUSEL' || input.media.some((m) => m.kind === 'VIDEO');
    if (needsPolling) await this.#awaitContainerReady(ctx, containerId);

    const published = await request<PublishResponse>(
      {
        method: 'POST',
        url: buildUrl(this.#base, `${ctx.platformAccountId}/media_publish`, {}),
        form: { creation_id: containerId, access_token: ctx.accessToken },
      },
      'INSTAGRAM',
    );

    return {
      platformPostId: published.body.id,
      platformUrl: `https://www.instagram.com/p/${published.body.id}/`,
      publishedAt: new Date(),
      scheduledByPlatform: false,
      raw: published.body,
    };
  }

  async #createSingleContainer(ctx: AdapterContext, input: CreatePostInput): Promise<string> {
    const item = input.media[0];
    if (!item) throw new ValidationError('No media supplied');

    const form: Record<string, string> = {
      caption: input.caption,
      access_token: ctx.accessToken,
    };

    if (input.kind === 'REEL' || (input.kind === 'VIDEO' && item.kind === 'VIDEO')) {
      form['media_type'] = 'REELS';
      form['video_url'] = item.url;
      if (input.thumbnailUrl) form['thumb_offset'] = '0';
    } else if (input.kind === 'STORY') {
      form['media_type'] = 'STORIES';
      if (item.kind === 'VIDEO') form['video_url'] = item.url;
      else form['image_url'] = item.url;
      delete form['caption']; // stories take no caption
    } else {
      form['image_url'] = item.url;
    }

    const res = await request<ContainerResponse>(
      { method: 'POST', url: buildUrl(this.#base, `${ctx.platformAccountId}/media`, {}), form },
      'INSTAGRAM',
    );
    return res.body.id;
  }

  async #createCarouselContainer(ctx: AdapterContext, input: CreatePostInput): Promise<string> {
    // Children are created sequentially rather than in parallel: Meta's per-user
    // hourly call budget is small, and a burst here risks a 429 mid-carousel,
    // which would leave orphaned containers.
    const childIds: string[] = [];
    for (const item of input.media) {
      const form: Record<string, string> = {
        is_carousel_item: 'true',
        access_token: ctx.accessToken,
      };
      if (item.kind === 'VIDEO') {
        form['media_type'] = 'VIDEO';
        form['video_url'] = item.url;
      } else {
        form['image_url'] = item.url;
      }
      const child = await request<ContainerResponse>(
        { method: 'POST', url: buildUrl(this.#base, `${ctx.platformAccountId}/media`, {}), form },
        'INSTAGRAM',
      );
      childIds.push(child.body.id);
    }

    const parent = await request<ContainerResponse>(
      {
        method: 'POST',
        url: buildUrl(this.#base, `${ctx.platformAccountId}/media`, {}),
        form: {
          media_type: 'CAROUSEL',
          children: childIds.join(','),
          caption: input.caption,
          access_token: ctx.accessToken,
        },
      },
      'INSTAGRAM',
    );
    return parent.body.id;
  }

  /** Poll until the container finishes transcoding, or give up with a clear error. */
  async #awaitContainerReady(
    ctx: AdapterContext,
    containerId: string,
    { timeoutMs = 5 * 60_000, intervalMs = 5_000 }: { timeoutMs?: number; intervalMs?: number } = {},
  ): Promise<void> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const res = await request<ContainerStatusResponse>(
        {
          method: 'GET',
          url: buildUrl(this.#base, containerId, {
            fields: 'status_code,status',
            access_token: ctx.accessToken,
          }),
        },
        'INSTAGRAM',
      );
      const code = res.body.status_code ?? '';
      if (code === 'FINISHED') return;
      if (TERMINAL_CONTAINER_ERRORS.has(code)) {
        throw new PlatformApiError(
          'INSTAGRAM',
          `Media container ${code}: ${res.body.status ?? 'no detail provided'}`,
          { retryable: false, context: { containerId } },
        );
      }
      await sleep(intervalMs);
    }
    throw new PlatformApiError('INSTAGRAM', `Media container was not ready within ${timeoutMs / 1000}s`, {
      retryable: true,
      context: { containerId },
    });
  }

  async getPostStatus(ctx: AdapterContext, ref: string): Promise<PostStatus> {
    const res = await request<ContainerStatusResponse>(
      {
        method: 'GET',
        url: buildUrl(this.#base, ref, { fields: 'status_code,status', access_token: ctx.accessToken }),
      },
      'INSTAGRAM',
    );
    const code = res.body.status_code;
    const state =
      code === 'FINISHED' ? 'PUBLISHED' : code === 'ERROR' || code === 'EXPIRED' ? 'FAILED' : 'PROCESSING';
    return {
      state,
      platformPostId: ref,
      ...(res.body.status ? { error: res.body.status } : {}),
      raw: res.body,
    };
  }

  /* ------------------------------ analytics ------------------------------ */

  async getAnalytics(ctx: AdapterContext, platformPostId: string): Promise<NormalizedAnalytics> {
    // Deliberately requests only live metrics. Asking for a deprecated metric
    // returns an error for the whole call, not a partial result.
    const res = await request<{ data?: Array<{ name: string; values?: Array<{ value: number }> }> }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, `${platformPostId}/insights`, {
          metric: IG_MEDIA_METRICS.join(','),
          access_token: ctx.accessToken,
        }),
      },
      'INSTAGRAM',
    );

    const values = new Map<string, number>();
    for (const entry of res.body.data ?? []) {
      const v = entry.values?.[0]?.value;
      if (typeof v === 'number') values.set(entry.name, v);
    }

    const likes = values.get('likes') ?? null;
    const comments = values.get('comments') ?? null;
    const shares = values.get('shares') ?? null;
    const saves = values.get('saved') ?? null;
    const reach = values.get('reach') ?? null;
    const interactions = values.get('total_interactions') ?? sumOrNull([likes, comments, shares, saves]);

    return {
      platformPostId,
      collectedAt: new Date(),
      views: values.get('views') ?? null,
      reach,
      impressions: null, // deprecated by Meta — absent, not zero
      likes,
      comments,
      shares,
      saves,
      watchTimeSec: values.get('ig_reels_video_view_total_time') ?? null,
      avgWatchTimeSec: values.get('ig_reels_avg_watch_time') ?? null,
      retentionRate: null,
      profileVisits: null, // deprecated
      followsGained: null,
      clicks: null, // deprecated
      engagementRate: reach && interactions !== null && reach > 0 ? interactions / reach : null,
      unavailableMetrics: [...IG_DEPRECATED_METRICS],
      raw: res.body,
    };
  }

  async getAccountAnalytics(ctx: AdapterContext): Promise<AccountAnalytics> {
    const res = await request<{ data?: Array<{ name: string; values?: Array<{ value: number }> }> }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, `${ctx.platformAccountId}/insights`, {
          metric: IG_ACCOUNT_METRICS.join(','),
          period: 'day',
          metric_type: 'total_value',
          access_token: ctx.accessToken,
        }),
      },
      'INSTAGRAM',
    );
    const values = new Map<string, number>();
    for (const entry of res.body.data ?? []) {
      const v = entry.values?.[0]?.value;
      if (typeof v === 'number') values.set(entry.name, v);
    }
    const account = await this.getAccount(ctx);
    return {
      collectedAt: new Date(),
      followerCount: account.followerCount ?? null,
      reach: values.get('reach') ?? null,
      views: values.get('views') ?? null,
      unavailableMetrics: [...IG_DEPRECATED_METRICS],
      raw: res.body,
    };
  }

  /* --------------------------- unsupported ops --------------------------- */

  async deletePost(_ctx: AdapterContext, _platformPostId: string): Promise<void> {
    throw new CapabilityNotSupportedError(
      'Instagram',
      'delete post',
      'The Graph API exposes no delete endpoint for API-published media. Remove the post manually in the Instagram app.',
    );
  }

  async updatePost(ctx: AdapterContext, platformPostId: string, caption: string): Promise<void> {
    await request(
      {
        method: 'POST',
        url: buildUrl(this.#base, platformPostId, {}),
        form: { caption, access_token: ctx.accessToken },
      },
      'INSTAGRAM',
    );
  }
}

function sumOrNull(values: Array<number | null>): number | null {
  const present = values.filter((v): v is number => v !== null);
  return present.length === 0 ? null : present.reduce((a, b) => a + b, 0);
}
