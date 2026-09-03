/**
 * Facebook Pages adapter — Meta Graph API.
 *
 * The interesting difference from Instagram: Facebook supports genuine native
 * scheduling (published=false + scheduled_publish_time). When a future time is
 * supplied we hand it to Facebook and let Facebook do the waiting, rather than
 * holding the job in our own scheduler. That is the concrete payoff of the
 * capability registry: the same CreatePostInput takes two different paths
 * because the platforms genuinely differ.
 */
import { CapabilityNotSupportedError, ValidationError } from '@mmos/core';
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
import { FACEBOOK_CAPABILITIES } from '../capabilities.js';
import { buildUrl, request } from '../http.js';
import { validateAgainstCapabilities } from '../validation.js';

export interface FacebookAdapterConfig {
  appId: string;
  appSecret: string;
  redirectUri: string;
  graphVersion: string;
  baseUrl?: string;
}

export class FacebookAdapter implements PlatformAdapter {
  readonly platform = 'FACEBOOK' as const;
  readonly #config: FacebookAdapterConfig;
  readonly #base: string;

  constructor(config: FacebookAdapterConfig) {
    this.#config = config;
    this.#base = `${config.baseUrl ?? 'https://graph.facebook.com'}/${config.graphVersion}/`;
  }

  getPublishingCapabilities(): PlatformCapabilities {
    return FACEBOOK_CAPABILITIES;
  }

  /* -------------------------------- OAuth -------------------------------- */

  getAuthorizationUrl(state: string, scopes?: string[]): string {
    return buildUrl('https://www.facebook.com', `${this.#config.graphVersion}/dialog/oauth`, {
      client_id: this.#config.appId,
      redirect_uri: this.#config.redirectUri,
      state,
      response_type: 'code',
      scope: (scopes ?? FACEBOOK_CAPABILITIES.requiredScopes).join(','),
    });
  }

  async exchangeCodeForTokens(code: string): Promise<OAuthTokens> {
    const short = await request<{ access_token: string }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, 'oauth/access_token', {
          client_id: this.#config.appId,
          client_secret: this.#config.appSecret,
          redirect_uri: this.#config.redirectUri,
          code,
        }),
      },
      'FACEBOOK',
    );
    return this.refreshToken(short.body.access_token);
  }

  async refreshToken(currentToken: string): Promise<OAuthTokens> {
    const res = await request<{ access_token: string; expires_in?: number }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, 'oauth/access_token', {
          grant_type: 'fb_exchange_token',
          client_id: this.#config.appId,
          client_secret: this.#config.appSecret,
          fb_exchange_token: currentToken,
        }),
      },
      'FACEBOOK',
    );
    const expiresIn = res.body.expires_in ?? 60 * 24 * 3600;
    return {
      accessToken: res.body.access_token,
      refreshToken: null,
      expiresAt: new Date(Date.now() + expiresIn * 1000),
      scopes: [...FACEBOOK_CAPABILITIES.requiredScopes],
      raw: res.body,
    };
  }

  /**
   * Pages the user administers, each with its own Page access token. Publishing
   * uses the Page token, never the user token.
   */
  async listPages(userAccessToken: string): Promise<
    Array<{ id: string; name: string; accessToken: string; category?: string }>
  > {
    const res = await request<{
      data?: Array<{ id: string; name: string; access_token: string; category?: string }>;
    }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, 'me/accounts', {
          fields: 'id,name,access_token,category',
          access_token: userAccessToken,
        }),
      },
      'FACEBOOK',
    );
    return (res.body.data ?? []).map((p) => ({
      id: p.id,
      name: p.name,
      accessToken: p.access_token,
      ...(p.category ? { category: p.category } : {}),
    }));
  }

  /* ------------------------------- account ------------------------------- */

  async getAccount(ctx: AdapterContext): Promise<PlatformAccount> {
    const res = await request<{
      id: string;
      name: string;
      username?: string;
      fan_count?: number;
      followers_count?: number;
      picture?: { data?: { url?: string } };
    }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, ctx.platformAccountId, {
          fields: 'id,name,username,fan_count,followers_count,picture{url}',
          access_token: ctx.accessToken,
        }),
      },
      'FACEBOOK',
    );
    const b = res.body;
    const followers = b.followers_count ?? b.fan_count;
    return {
      platformAccountId: b.id,
      username: b.username ?? b.name,
      displayName: b.name,
      ...(b.picture?.data?.url ? { profileImageUrl: b.picture.data.url } : {}),
      ...(followers !== undefined ? { followerCount: followers } : {}),
      accountType: 'PAGE',
      raw: b,
    };
  }

  /** Facebook publishes no equivalent of Instagram's content_publishing_limit. */
  async checkRateLimit(): Promise<RateLimitStatus> {
    return { canPublish: true };
  }

  /* ------------------------------ publishing ----------------------------- */

  validate(input: CreatePostInput): ValidationIssue[] {
    return validateAgainstCapabilities(input, FACEBOOK_CAPABILITIES);
  }

  async createPost(ctx: AdapterContext, input: CreatePostInput): Promise<PublishResult> {
    const errors = this.validate(input).filter((i) => i.severity === 'ERROR');
    if (errors.length > 0) {
      throw new ValidationError(`Facebook validation failed: ${errors.map((e) => e.message).join('; ')}`, {
        issues: errors,
      });
    }

    // Native scheduling: hand the timestamp to Facebook.
    const scheduling: Record<string, string> = {};
    const isScheduled = Boolean(input.scheduledAt && input.scheduledAt.getTime() > Date.now() + 60_000);
    if (isScheduled && input.scheduledAt) {
      scheduling['published'] = 'false';
      scheduling['scheduled_publish_time'] = String(Math.floor(input.scheduledAt.getTime() / 1000));
    }

    const video = input.media.find((m) => m.kind === 'VIDEO');
    const result = video
      ? await this.#postVideo(ctx, input, video.url, scheduling)
      : await this.#postPhotos(ctx, input, scheduling);

    return {
      ...result,
      publishedAt: input.scheduledAt && isScheduled ? input.scheduledAt : new Date(),
      scheduledByPlatform: isScheduled,
    };
  }

  async #postVideo(
    ctx: AdapterContext,
    input: CreatePostInput,
    videoUrl: string,
    scheduling: Record<string, string>,
  ): Promise<Omit<PublishResult, 'publishedAt'>> {
    const res = await request<{ id: string; post_id?: string }>(
      {
        method: 'POST',
        url: buildUrl(this.#base, `${ctx.platformAccountId}/videos`, {}),
        form: {
          file_url: videoUrl,
          description: input.caption,
          access_token: ctx.accessToken,
          ...scheduling,
        },
      },
      'FACEBOOK',
    );
    const id = res.body.post_id ?? res.body.id;
    return { platformPostId: id, platformUrl: `https://www.facebook.com/${id}`, raw: res.body };
  }

  async #postPhotos(
    ctx: AdapterContext,
    input: CreatePostInput,
    scheduling: Record<string, string>,
  ): Promise<Omit<PublishResult, 'publishedAt'>> {
    const images = input.media.filter((m) => m.kind === 'IMAGE');

    if (images.length === 1 && images[0]) {
      const res = await request<{ id: string; post_id?: string }>(
        {
          method: 'POST',
          url: buildUrl(this.#base, `${ctx.platformAccountId}/photos`, {}),
          form: {
            url: images[0].url,
            caption: input.caption,
            access_token: ctx.accessToken,
            ...scheduling,
          },
        },
        'FACEBOOK',
      );
      const id = res.body.post_id ?? res.body.id;
      return { platformPostId: id, platformUrl: `https://www.facebook.com/${id}`, raw: res.body };
    }

    // Multi-photo: upload each unpublished, then attach the ids to a feed post.
    const mediaFbids: string[] = [];
    for (const img of images) {
      const uploaded = await request<{ id: string }>(
        {
          method: 'POST',
          url: buildUrl(this.#base, `${ctx.platformAccountId}/photos`, {}),
          form: { url: img.url, published: 'false', access_token: ctx.accessToken },
        },
        'FACEBOOK',
      );
      mediaFbids.push(uploaded.body.id);
    }

    const form: Record<string, string> = {
      message: input.caption,
      access_token: ctx.accessToken,
      ...scheduling,
    };
    mediaFbids.forEach((id, i) => {
      form[`attached_media[${i}]`] = JSON.stringify({ media_fbid: id });
    });

    const res = await request<{ id: string }>(
      { method: 'POST', url: buildUrl(this.#base, `${ctx.platformAccountId}/feed`, {}), form },
      'FACEBOOK',
    );
    return {
      platformPostId: res.body.id,
      platformUrl: `https://www.facebook.com/${res.body.id}`,
      raw: res.body,
    };
  }

  async getPostStatus(ctx: AdapterContext, platformPostId: string): Promise<PostStatus> {
    const res = await request<{ id: string; is_published?: boolean; scheduled_publish_time?: number }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, platformPostId, {
          fields: 'id,is_published,scheduled_publish_time',
          access_token: ctx.accessToken,
        }),
      },
      'FACEBOOK',
    );
    return {
      state: res.body.is_published === false ? 'SCHEDULED' : 'PUBLISHED',
      platformPostId: res.body.id,
      raw: res.body,
    };
  }

  /* ------------------------------ analytics ------------------------------ */

  async getAnalytics(ctx: AdapterContext, platformPostId: string): Promise<NormalizedAnalytics> {
    const metrics = [
      'post_impressions',
      'post_impressions_unique',
      'post_reactions_by_type_total',
      'post_clicks',
      'post_video_view_time',
    ];
    const res = await request<{ data?: Array<{ name: string; values?: Array<{ value: unknown }> }> }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, `${platformPostId}/insights`, {
          metric: metrics.join(','),
          access_token: ctx.accessToken,
        }),
      },
      'FACEBOOK',
    );

    const values = new Map<string, unknown>();
    for (const entry of res.body.data ?? []) values.set(entry.name, entry.values?.[0]?.value);

    const numeric = (k: string): number | null => {
      const v = values.get(k);
      return typeof v === 'number' ? v : null;
    };
    const reactions = values.get('post_reactions_by_type_total');
    const likes =
      reactions && typeof reactions === 'object'
        ? Object.values(reactions as Record<string, number>).reduce((a, b) => a + b, 0)
        : null;

    const reach = numeric('post_impressions_unique');
    const impressions = numeric('post_impressions');
    const clicks = numeric('post_clicks');

    return {
      platformPostId,
      collectedAt: new Date(),
      views: impressions,
      reach,
      impressions,
      likes,
      comments: null, // requires a separate edge read; not fetched here
      shares: null,
      saves: null,
      watchTimeSec: numeric('post_video_view_time'),
      avgWatchTimeSec: null,
      retentionRate: null,
      profileVisits: null,
      followsGained: null,
      clicks,
      engagementRate: reach && likes !== null && reach > 0 ? likes / reach : null,
      unavailableMetrics: ['saves', 'retention', 'profileVisits', 'follows'],
      raw: res.body,
    };
  }

  async getAccountAnalytics(ctx: AdapterContext): Promise<AccountAnalytics> {
    const res = await request<{ data?: Array<{ name: string; values?: Array<{ value: number }> }> }>(
      {
        method: 'GET',
        url: buildUrl(this.#base, `${ctx.platformAccountId}/insights`, {
          metric: 'page_impressions_unique,page_post_engagements',
          period: 'day',
          access_token: ctx.accessToken,
        }),
      },
      'FACEBOOK',
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
      reach: values.get('page_impressions_unique') ?? null,
      views: null,
      unavailableMetrics: ['views'],
      raw: res.body,
    };
  }

  /* --------------------------- supported ops ----------------------------- */

  async deletePost(ctx: AdapterContext, platformPostId: string): Promise<void> {
    await request(
      {
        method: 'DELETE',
        url: buildUrl(this.#base, platformPostId, { access_token: ctx.accessToken }),
      },
      'FACEBOOK',
    );
  }

  async updatePost(ctx: AdapterContext, platformPostId: string, caption: string): Promise<void> {
    if (!FACEBOOK_CAPABILITIES.canUpdate) {
      throw new CapabilityNotSupportedError('Facebook', 'edit post', 'Capability disabled in the registry.');
    }
    await request(
      {
        method: 'POST',
        url: buildUrl(this.#base, platformPostId, {}),
        form: { message: caption, access_token: ctx.accessToken },
      },
      'FACEBOOK',
    );
  }
}
