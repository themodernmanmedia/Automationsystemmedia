/**
 * Instagram adapter tests.
 *
 * All platform HTTP is mocked with nock. No test ever touches a real social
 * account — nock.disableNetConnect() makes that structurally impossible.
 */
import { afterEach, beforeAll, afterAll, describe, expect, it } from 'vitest';
import nock from 'nock';
import { InstagramAdapter } from './adapter.js';
import { CapabilityNotSupportedError, ValidationError } from '@mmos/core';
import type { AdapterContext, CreatePostInput } from '../types.js';

const GRAPH = 'https://graph.facebook.com';
const VERSION = 'v21.0';
const IG_ID = '17841400000000000';

const adapter = new InstagramAdapter({
  appId: 'test-app-id',
  appSecret: 'test-app-secret',
  redirectUri: 'https://example.com/callback',
  graphVersion: VERSION,
});

const ctx: AdapterContext = { accessToken: 'test-token', platformAccountId: IG_ID };

const imagePost = (overrides: Partial<CreatePostInput> = {}): CreatePostInput => ({
  kind: 'IMAGE',
  media: [
    {
      url: 'https://cdn.example.com/slide.jpg',
      kind: 'IMAGE',
      mimeType: 'image/jpeg',
      width: 1080,
      height: 1350,
      fileSizeBytes: 500_000,
    },
  ],
  caption: 'The Modern Man — test caption',
  ...overrides,
});

/** Publishing always checks the rolling quota first. */
function mockQuota(used = 5, total = 100) {
  nock(GRAPH)
    .get(`/${VERSION}/${IG_ID}/content_publishing_limit`)
    .query(true)
    .reply(200, { data: [{ quota_usage: used, config: { quota_total: total } }] });
}

beforeAll(() => {
  nock.disableNetConnect();
});
afterAll(() => {
  nock.enableNetConnect();
});
afterEach(() => {
  nock.cleanAll();
});

describe('capabilities', () => {
  it('declares that Instagram cannot schedule natively', () => {
    const caps = adapter.getPublishingCapabilities();
    expect(caps.canSchedule).toBe(false);
    expect(caps.scheduleStrategy).toBe('SELF_TIMED');
    expect(caps.notes['canSchedule']).toMatch(/no scheduled_publish_time/i);
  });

  it('declares that Instagram media must be pulled from a public URL', () => {
    expect(adapter.getPublishingCapabilities().mediaDelivery).toBe('PULL_FROM_URL');
  });
});

describe('validation', () => {
  it('rejects a caption over 2200 characters', () => {
    const issues = adapter.validate(imagePost({ caption: 'x'.repeat(2201) }));
    expect(issues.some((i) => i.severity === 'ERROR' && i.field === 'caption')).toBe(true);
  });

  it('rejects more than 30 hashtags', () => {
    const caption = Array.from({ length: 31 }, (_, i) => `#tag${i}`).join(' ');
    const issues = adapter.validate(imagePost({ caption }));
    expect(issues.some((i) => i.message.includes('hashtags'))).toBe(true);
  });

  it('rejects a carousel with more than 10 items', () => {
    const media = Array.from({ length: 11 }, (_, i) => ({
      url: `https://cdn.example.com/${i}.jpg`,
      kind: 'IMAGE' as const,
      mimeType: 'image/jpeg',
      width: 1080,
      height: 1350,
    }));
    const issues = adapter.validate({ kind: 'CAROUSEL', media, caption: 'hi' });
    expect(issues.some((i) => i.message.includes('2-10 items'))).toBe(true);
  });

  it('rejects localhost media, which Meta cannot fetch', () => {
    const issues = adapter.validate(
      imagePost({
        media: [
          { url: 'http://localhost:3000/a.jpg', kind: 'IMAGE', mimeType: 'image/jpeg', width: 1080, height: 1350 },
        ],
      }),
    );
    expect(issues.some((i) => i.message.includes('publicly resolvable'))).toBe(true);
  });

  it('rejects a Reel longer than the 90-second API cap', () => {
    const issues = adapter.validate({
      kind: 'REEL',
      caption: 'test',
      media: [
        {
          url: 'https://cdn.example.com/r.mp4',
          kind: 'VIDEO',
          mimeType: 'video/mp4',
          width: 1080,
          height: 1920,
          durationSec: 120,
        },
      ],
    });
    expect(issues.some((i) => i.message.includes('at most 90s'))).toBe(true);
  });

  it('accepts a well-formed 9:16 Reel', () => {
    const issues = adapter.validate({
      kind: 'REEL',
      caption: 'test',
      media: [
        {
          url: 'https://cdn.example.com/r.mp4',
          kind: 'VIDEO',
          mimeType: 'video/mp4',
          width: 1080,
          height: 1920,
          durationSec: 45,
          fileSizeBytes: 10_000_000,
        },
      ],
    });
    expect(issues.filter((i) => i.severity === 'ERROR')).toEqual([]);
  });
});

describe('publishing', () => {
  it('publishes an image via the two-step container flow', async () => {
    mockQuota();
    nock(GRAPH).post(`/${VERSION}/${IG_ID}/media`).reply(200, { id: 'container-1' });
    nock(GRAPH).post(`/${VERSION}/${IG_ID}/media_publish`).reply(200, { id: 'media-123' });

    const result = await adapter.createPost(ctx, imagePost());
    expect(result.platformPostId).toBe('media-123');
    expect(result.scheduledByPlatform).toBe(false);
  });

  it('creates one child container per carousel item plus a parent', async () => {
    mockQuota();
    const created: string[] = [];
    nock(GRAPH)
      .post(`/${VERSION}/${IG_ID}/media`)
      .times(4)
      .reply(200, function (_uri, body) {
        created.push(String(body));
        return { id: `c-${created.length}` };
      });
    // The parent container is assembled asynchronously, so the adapter polls it
    // before publishing — mock that status check.
    nock(GRAPH)
      .get(`/${VERSION}/c-4`)
      .query(true)
      .reply(200, { id: 'c-4', status_code: 'FINISHED' });
    nock(GRAPH).post(`/${VERSION}/${IG_ID}/media_publish`).reply(200, { id: 'carousel-post' });

    const media = Array.from({ length: 3 }, (_, i) => ({
      url: `https://cdn.example.com/${i}.jpg`,
      kind: 'IMAGE' as const,
      mimeType: 'image/jpeg',
      width: 1080,
      height: 1350,
    }));

    const result = await adapter.createPost(ctx, { kind: 'CAROUSEL', media, caption: 'Carousel' });

    expect(result.platformPostId).toBe('carousel-post');
    // 3 children + 1 parent
    expect(created).toHaveLength(4);
    expect(created.filter((b) => b.includes('is_carousel_item'))).toHaveLength(3);
    expect(created.some((b) => b.includes('CAROUSEL'))).toBe(true);
  });

  it('polls the container until it reports FINISHED before publishing a Reel', async () => {
    mockQuota();
    nock(GRAPH).post(`/${VERSION}/${IG_ID}/media`).reply(200, { id: 'vid-container' });
    nock(GRAPH)
      .get(`/${VERSION}/vid-container`)
      .query(true)
      .reply(200, { id: 'vid-container', status_code: 'IN_PROGRESS' });
    nock(GRAPH)
      .get(`/${VERSION}/vid-container`)
      .query(true)
      .reply(200, { id: 'vid-container', status_code: 'FINISHED' });
    nock(GRAPH).post(`/${VERSION}/${IG_ID}/media_publish`).reply(200, { id: 'reel-987' });

    const result = await adapter.createPost(ctx, {
      kind: 'REEL',
      caption: 'Reel caption',
      media: [
        {
          url: 'https://cdn.example.com/r.mp4',
          kind: 'VIDEO',
          mimeType: 'video/mp4',
          width: 1080,
          height: 1920,
          durationSec: 30,
        },
      ],
    });
    expect(result.platformPostId).toBe('reel-987');
    expect(nock.isDone()).toBe(true);
  }, 30_000);

  it('refuses to publish when the rolling 24h quota is exhausted', async () => {
    mockQuota(100, 100);
    await expect(adapter.createPost(ctx, imagePost())).rejects.toThrow(/publishing limit reached/i);
  });

  it('refuses a future scheduledAt rather than publishing early', async () => {
    await expect(
      adapter.createPost(ctx, imagePost({ scheduledAt: new Date(Date.now() + 3_600_000) })),
    ).rejects.toBeInstanceOf(CapabilityNotSupportedError);
  });

  it('rejects invalid input before making any API call', async () => {
    await expect(adapter.createPost(ctx, imagePost({ caption: 'x'.repeat(3000) }))).rejects.toBeInstanceOf(
      ValidationError,
    );
    // Nothing was requested, so the quota mock was never needed.
    expect(nock.pendingMocks()).toEqual([]);
  });
});

describe('unsupported operations', () => {
  it('throws rather than pretending a delete succeeded', async () => {
    await expect(adapter.deletePost(ctx, 'media-123')).rejects.toBeInstanceOf(CapabilityNotSupportedError);
    await expect(adapter.deletePost(ctx, 'media-123')).rejects.toThrow(/NOT SUPPORTED BY CURRENT API/);
  });
});

describe('analytics', () => {
  it('normalizes insights and reports deprecated metrics as unavailable, not zero', async () => {
    nock(GRAPH)
      .get(`/${VERSION}/media-123/insights`)
      .query(true)
      .reply(200, {
        data: [
          { name: 'reach', values: [{ value: 10_000 }] },
          { name: 'likes', values: [{ value: 500 }] },
          { name: 'comments', values: [{ value: 40 }] },
          { name: 'shares', values: [{ value: 60 }] },
          { name: 'saved', values: [{ value: 400 }] },
          { name: 'views', values: [{ value: 25_000 }] },
          { name: 'total_interactions', values: [{ value: 1000 }] },
        ],
      });

    const a = await adapter.getAnalytics(ctx, 'media-123');
    expect(a.views).toBe(25_000);
    expect(a.saves).toBe(400);
    // Critically: null, not 0 — a fabricated zero would poison the learning engine.
    expect(a.impressions).toBeNull();
    expect(a.profileVisits).toBeNull();
    expect(a.unavailableMetrics).toContain('impressions');
    expect(a.engagementRate).toBeCloseTo(0.1, 5);
  });

  it('never requests a deprecated metric', async () => {
    let requestedMetrics = '';
    nock(GRAPH)
      .get(`/${VERSION}/media-123/insights`)
      .query((q) => {
        requestedMetrics = String(q['metric'] ?? '');
        return true;
      })
      .reply(200, { data: [] });

    await adapter.getAnalytics(ctx, 'media-123');
    for (const dead of ['impressions', 'plays', 'video_views', 'profile_views']) {
      expect(requestedMetrics.split(',')).not.toContain(dead);
    }
  });
});

describe('oauth', () => {
  it('exchanges the code and immediately upgrades to a long-lived token', async () => {
    nock(GRAPH)
      .get(`/${VERSION}/oauth/access_token`)
      .query((q) => q['code'] === 'auth-code')
      .reply(200, { access_token: 'short-lived', expires_in: 3600 });
    nock(GRAPH)
      .get(`/${VERSION}/oauth/access_token`)
      .query((q) => q['grant_type'] === 'fb_exchange_token')
      .reply(200, { access_token: 'long-lived-token', expires_in: 5_184_000 });

    const tokens = await adapter.exchangeCodeForTokens('auth-code');
    expect(tokens.accessToken).toBe('long-lived-token');
    // ~60 days out, not ~1 hour.
    expect(tokens.expiresAt!.getTime() - Date.now()).toBeGreaterThan(50 * 24 * 3600 * 1000);
  });
});
