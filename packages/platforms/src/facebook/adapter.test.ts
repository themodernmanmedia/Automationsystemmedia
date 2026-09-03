/**
 * Facebook adapter tests.
 *
 * Facebook is the one platform of the three with genuine native scheduling, so
 * the tests focus on proving the delegated path is actually taken.
 */
import { afterEach, describe, expect, it } from 'vitest';
import nock from 'nock';
import { FacebookAdapter } from './adapter.js';
import type { AdapterContext, CreatePostInput } from '../types.js';

const GRAPH = 'https://graph.facebook.com';
const VERSION = 'v21.0';
const PAGE_ID = '1234567890';

const adapter = new FacebookAdapter({
  appId: 'app',
  appSecret: 'secret',
  redirectUri: 'https://example.com/cb',
  graphVersion: VERSION,
});

const ctx: AdapterContext = { accessToken: 'page-token', platformAccountId: PAGE_ID };

const imagePost = (overrides: Partial<CreatePostInput> = {}): CreatePostInput => ({
  kind: 'IMAGE',
  caption: 'Test post',
  media: [
    { url: 'https://cdn.example.com/a.jpg', kind: 'IMAGE', mimeType: 'image/jpeg', width: 1200, height: 630 },
  ],
  ...overrides,
});

afterEach(() => nock.cleanAll());

describe('capabilities', () => {
  it('declares native scheduling, unlike Instagram and TikTok', () => {
    const caps = adapter.getPublishingCapabilities();
    expect(caps.canSchedule).toBe(true);
    expect(caps.scheduleStrategy).toBe('DELEGATED');
    expect(caps.canDelete).toBe(true);
  });
});

describe('scheduling', () => {
  it('delegates timing to Facebook with published=false and a Unix timestamp', async () => {
    const scheduledAt = new Date(Date.now() + 2 * 3600 * 1000);
    let sentBody = '';
    nock(GRAPH)
      .post(`/${VERSION}/${PAGE_ID}/photos`, (body) => {
        sentBody = new URLSearchParams(body as Record<string, string>).toString();
        return true;
      })
      .reply(200, { id: 'photo-1', post_id: 'post-1' });

    const result = await adapter.createPost(ctx, imagePost({ scheduledAt }));

    expect(result.scheduledByPlatform).toBe(true);
    expect(sentBody).toContain('published=false');
    expect(sentBody).toContain(`scheduled_publish_time=${Math.floor(scheduledAt.getTime() / 1000)}`);
    // The platform holds it, so publishedAt reflects the intended time.
    expect(result.publishedAt.getTime()).toBe(scheduledAt.getTime());
  });

  it('publishes immediately when no time is given', async () => {
    let sentBody = '';
    nock(GRAPH)
      .post(`/${VERSION}/${PAGE_ID}/photos`, (body) => {
        sentBody = new URLSearchParams(body as Record<string, string>).toString();
        return true;
      })
      .reply(200, { id: 'photo-2' });

    const result = await adapter.createPost(ctx, imagePost());
    expect(result.scheduledByPlatform).toBe(false);
    expect(sentBody).not.toContain('published=false');
  });

  it('rejects a scheduled time less than 10 minutes out', () => {
    const issues = adapter.validate(imagePost({ scheduledAt: new Date(Date.now() + 60_000) }));
    expect(issues.some((i) => i.message.includes('at least 10 minutes'))).toBe(true);
  });

  it('rejects a scheduled time beyond the 30-day ceiling', () => {
    const issues = adapter.validate(imagePost({ scheduledAt: new Date(Date.now() + 31 * 86_400_000) }));
    expect(issues.some((i) => i.message.includes('at most 30 days'))).toBe(true);
  });
});

describe('multi-photo posts', () => {
  it('uploads each photo unpublished then attaches them to one feed post', async () => {
    nock(GRAPH).post(`/${VERSION}/${PAGE_ID}/photos`).reply(200, { id: 'm1' });
    nock(GRAPH).post(`/${VERSION}/${PAGE_ID}/photos`).reply(200, { id: 'm2' });

    let feedBody = '';
    nock(GRAPH)
      .post(`/${VERSION}/${PAGE_ID}/feed`, (body) => {
        feedBody = new URLSearchParams(body as Record<string, string>).toString();
        return true;
      })
      .reply(200, { id: 'feed-1' });

    const media = ['a', 'b'].map((n) => ({
      url: `https://cdn.example.com/${n}.jpg`,
      kind: 'IMAGE' as const,
      mimeType: 'image/jpeg',
      width: 1200,
      height: 630,
    }));

    const result = await adapter.createPost(ctx, { kind: 'CAROUSEL', caption: 'Carousel', media });
    expect(result.platformPostId).toBe('feed-1');
    expect(decodeURIComponent(feedBody)).toContain('media_fbid":"m1');
    expect(decodeURIComponent(feedBody)).toContain('media_fbid":"m2');
  });
});

describe('supported operations', () => {
  it('deletes a post, which Facebook does allow', async () => {
    nock(GRAPH).delete(`/${VERSION}/post-1`).query(true).reply(200, { success: true });
    await expect(adapter.deletePost(ctx, 'post-1')).resolves.toBeUndefined();
  });
});

describe('pages', () => {
  it('lists pages with their per-page access tokens', async () => {
    nock(GRAPH)
      .get(`/${VERSION}/me/accounts`)
      .query(true)
      .reply(200, { data: [{ id: 'p1', name: 'The Modern Man', access_token: 'page-tok', category: 'Media' }] });

    const pages = await adapter.listPages('user-token');
    expect(pages).toHaveLength(1);
    expect(pages[0]!.accessToken).toBe('page-tok');
  });
});
