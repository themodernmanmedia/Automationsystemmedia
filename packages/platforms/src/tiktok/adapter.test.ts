/**
 * TikTok adapter tests.
 *
 * The behaviors worth guarding are the two that are easy to get wrong and
 * expensive when wrong: honoring creator_info constraints, and telling the truth
 * about forced-private visibility for unaudited clients.
 */
import { afterEach, describe, expect, it } from 'vitest';
import nock from 'nock';
import { TikTokAdapter } from './adapter.js';
import { CapabilityNotSupportedError } from '@mmos/core';
import type { AdapterContext, CreatePostInput } from '../types.js';

const API = 'https://open.tiktokapis.com';

const adapter = new TikTokAdapter({
  clientKey: 'test-key',
  clientSecret: 'test-secret',
  redirectUri: 'https://example.com/cb',
});

const ctx: AdapterContext = { accessToken: 'tt-token', platformAccountId: 'open-id-1', isAudited: false };
const auditedCtx: AdapterContext = { ...ctx, isAudited: true };

function mockCreatorInfo(overrides: Record<string, unknown> = {}) {
  nock(API)
    .post('/v2/post/publish/creator_info/query/')
    .reply(200, {
      data: {
        creator_nickname: 'The Modern Man',
        privacy_level_options: ['PUBLIC_TO_EVERYONE', 'SELF_ONLY'],
        comment_disabled: false,
        duet_disabled: false,
        stitch_disabled: false,
        max_video_post_duration_sec: 180,
        ...overrides,
      },
      error: { code: 'ok' },
    });
}

const videoPost = (overrides: Partial<CreatePostInput> = {}): CreatePostInput => ({
  kind: 'VIDEO',
  caption: 'Test reel',
  privacyLevel: 'PUBLIC_TO_EVERYONE',
  media: [
    {
      url: 'https://cdn.example.com/v.mp4',
      kind: 'VIDEO',
      mimeType: 'video/mp4',
      width: 1080,
      height: 1920,
      durationSec: 30,
      fileSizeBytes: 8_000_000,
    },
  ],
  ...overrides,
});

afterEach(() => nock.cleanAll());

describe('capabilities', () => {
  it('documents the audit restriction and the absence of trend data', () => {
    const caps = adapter.getPublishingCapabilities();
    expect(caps.notes['audit']).toMatch(/SELF_ONLY/);
    expect(caps.notes['trends']).toMatch(/academic/i);
    expect(caps.canSchedule).toBe(false);
    expect(caps.canDelete).toBe(false);
  });
});

describe('creator info gate', () => {
  it('refuses a privacy level the creator has not permitted', async () => {
    mockCreatorInfo({ privacy_level_options: ['SELF_ONLY'] });
    await expect(
      adapter.createPost(ctx, videoPost({ privacyLevel: 'PUBLIC_TO_EVERYONE' })),
    ).rejects.toThrow(/not permitted for this creator/);
  });

  it('refuses a video longer than the creator-specific maximum', async () => {
    mockCreatorInfo({ max_video_post_duration_sec: 15 });
    await expect(
      adapter.createPost(ctx, videoPost({ media: [{ ...videoPost().media[0]!, durationSec: 60 }] })),
    ).rejects.toThrow(/creator's maximum is 15s/);
  });
});

describe('publishing', () => {
  function mockPublishFlow() {
    nock(API)
      .post('/v2/post/publish/video/init/')
      .reply(200, { data: { publish_id: 'pub-1' }, error: { code: 'ok' } });
    nock(API)
      .post('/v2/post/publish/status/fetch/')
      .reply(200, {
        data: { status: 'PUBLISH_COMPLETE', publicaly_available_post_id: ['tt-post-1'] },
        error: { code: 'ok' },
      });
  }

  it('publishes a video and flags forced-private visibility for an unaudited client', async () => {
    mockCreatorInfo();
    mockPublishFlow();

    const result = await adapter.createPost(ctx, videoPost());
    expect(result.platformPostId).toBe('tt-post-1');
    expect(result.restrictedVisibility).toBe(true);
    expect(result.visibilityNote).toMatch(/has not passed TikTok audit/);
  });

  it('does not flag restricted visibility once the client is audited', async () => {
    mockCreatorInfo();
    mockPublishFlow();

    const result = await adapter.createPost(auditedCtx, videoPost());
    expect(result.restrictedVisibility).toBe(false);
    expect(result.visibilityNote).toBeUndefined();
  });

  it('refuses a future scheduledAt rather than publishing early', async () => {
    await expect(
      adapter.createPost(ctx, videoPost({ scheduledAt: new Date(Date.now() + 3_600_000) })),
    ).rejects.toBeInstanceOf(CapabilityNotSupportedError);
  });

  it('surfaces a publish failure instead of reporting success', async () => {
    mockCreatorInfo();
    nock(API)
      .post('/v2/post/publish/video/init/')
      .reply(200, { data: { publish_id: 'pub-2' }, error: { code: 'ok' } });
    nock(API)
      .post('/v2/post/publish/status/fetch/')
      .reply(200, {
        data: { status: 'FAILED', fail_reason: 'video_format_check_failed' },
        error: { code: 'ok' },
      });

    await expect(adapter.createPost(ctx, videoPost())).rejects.toThrow(/video_format_check_failed/);
  });

  it('classifies a TikTok error envelope returned inside a 200 response', async () => {
    nock(API)
      .post('/v2/post/publish/creator_info/query/')
      .reply(200, { error: { code: 'spam_risk_too_many_posts', message: 'Too many posts' } });

    await expect(adapter.createPost(ctx, videoPost())).rejects.toThrow(/Too many posts/);
  });
});

describe('unsupported operations', () => {
  it('throws for delete and edit rather than silently doing nothing', async () => {
    await expect(adapter.deletePost()).rejects.toBeInstanceOf(CapabilityNotSupportedError);
    await expect(adapter.updatePost()).rejects.toBeInstanceOf(CapabilityNotSupportedError);
  });
});

describe('analytics', () => {
  it('marks metrics the Display API cannot provide as unavailable', async () => {
    nock(API)
      .post('/v2/video/query/')
      .query(true)
      .reply(200, {
        data: { videos: [{ id: 'v1', view_count: 10_000, like_count: 800, comment_count: 100, share_count: 100 }] },
        error: { code: 'ok' },
      });

    const a = await adapter.getAnalytics(ctx, 'v1');
    expect(a.views).toBe(10_000);
    expect(a.engagementRate).toBeCloseTo(0.1, 5);
    expect(a.reach).toBeNull();
    expect(a.saves).toBeNull();
    expect(a.unavailableMetrics).toContain('reach');
  });
});

describe('oauth', () => {
  it('returns both token lifetimes so the refresh worker can act in time', async () => {
    nock(API).post('/v2/oauth/token/').reply(200, {
      access_token: 'at',
      refresh_token: 'rt',
      expires_in: 86_400,
      refresh_expires_in: 31_536_000,
      scope: 'video.publish,video.upload',
      open_id: 'open-id-1',
    });

    const tokens = await adapter.exchangeCodeForTokens('code');
    expect(tokens.accessToken).toBe('at');
    expect(tokens.refreshToken).toBe('rt');
    expect(tokens.scopes).toContain('video.publish');
    // Access token is short-lived (~24h); refresh token is long.
    expect(tokens.expiresAt!.getTime() - Date.now()).toBeLessThan(2 * 86_400 * 1000);
    expect(tokens.refreshExpiresAt!.getTime() - Date.now()).toBeGreaterThan(300 * 86_400 * 1000);
  });
});

describe('validation', () => {
  it('rejects a video with no media', () => {
    const issues = adapter.validate({ kind: 'VIDEO', caption: 'x', media: [] });
    expect(issues.some((i) => i.severity === 'ERROR')).toBe(true);
  });
});
