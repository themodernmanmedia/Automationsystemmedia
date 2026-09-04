import { describe, expect, it, vi } from 'vitest';
import nock from 'nock';
import { RssSearchProvider } from './search.js';
import { AnthropicProvider } from './anthropic.js';
import { OpenAiProvider } from './openai.js';

const FEED = `<?xml version="1.0"?><rss version="2.0"><channel>
<item>
  <title>Why deep work beats busywork</title>
  <link>https://example.com/deep-work</link>
  <description><![CDATA[Focused blocks outperformed fragmented schedules.]]></description>
  <pubDate>Wed, 03 Sep 2026 12:00:00 GMT</pubDate>
</item>
<item>
  <title>Script link that must never be stored</title>
  <link>javascript:alert(1)</link>
  <description>Hostile entry.</description>
</item>
<item>
  <title>Credentialed link that must never be stored</title>
  <link>https://user:pw@example.com/x</link>
  <description>Hostile entry.</description>
</item>
</channel></rss>`;

describe('RssSearchProvider', () => {
  it('parses a real feed shape into search results', async () => {
    nock('https://feed.example.com').get('/rss.xml').reply(200, FEED, { 'content-type': 'application/rss+xml' });
    const results = await new RssSearchProvider({ feeds: ['https://feed.example.com/rss.xml'] }).fetchLatest();

    expect(results).toHaveLength(1);
    expect(results[0]).toMatchObject({
      title: 'Why deep work beats busywork',
      url: 'https://example.com/deep-work',
      publisher: 'feed.example.com',
    });
    expect(results[0]?.snippet).toContain('Focused blocks');
  });

  it('drops entries whose link is not an ordinary web URL', async () => {
    // The feed chooses these values. A `javascript:` or credentialed URL has no
    // legitimate reading, and it would otherwise be stored and later fetched.
    nock('https://feed.example.com').get('/rss.xml').reply(200, FEED);
    const results = await new RssSearchProvider({ feeds: ['https://feed.example.com/rss.xml'] }).fetchLatest();
    expect(results.map((r) => r.url)).toEqual(['https://example.com/deep-work']);
  });

  it('reports which feed failed and why, rather than looking empty', async () => {
    // A skipped feed used to be indistinguishable from an empty one, so a typo
    // in RSS_FEEDS surfaced only as "no items from any source".
    nock('https://feed.example.com').get('/broken.xml').reply(403, 'Forbidden');
    const warn = vi.fn();
    const results = await new RssSearchProvider({
      feeds: ['https://feed.example.com/broken.xml'],
      logger: { warn },
    }).fetchLatest();

    expect(results).toEqual([]);
    expect(warn).toHaveBeenCalledOnce();
    const [payload, message] = warn.mock.calls[0] as [{ failures: Array<{ feed: string; reason: string }> }, string];
    expect(message).toMatch(/could not be read/i);
    expect(payload.failures[0]?.feed).toBe('https://feed.example.com/broken.xml');
    expect(payload.failures[0]?.reason).toContain('403');
  });

  it('keeps working when one feed of several is broken', async () => {
    nock('https://feed.example.com').get('/rss.xml').reply(200, FEED);
    nock('https://broken.example.com').get('/rss.xml').replyWithError('ENOTFOUND');
    const results = await new RssSearchProvider({
      feeds: ['https://feed.example.com/rss.xml', 'https://broken.example.com/rss.xml'],
    }).fetchLatest();
    expect(results).toHaveLength(1);
  });
});

describe('model tiers', () => {
  it('defaults to the quality model and uses the fast model only when asked', () => {
    const anthropic = new AnthropicProvider({ apiKey: 'k', model: 'claude-opus-5', fastModel: 'claude-sonnet-5' });
    expect(anthropic.resolveModel({})).toBe('claude-opus-5');
    expect(anthropic.resolveModel({ tier: 'quality' })).toBe('claude-opus-5');
    expect(anthropic.resolveModel({ tier: 'fast' })).toBe('claude-sonnet-5');
  });

  it('lets an explicit model override the tier', () => {
    const anthropic = new AnthropicProvider({ apiKey: 'k', model: 'claude-opus-5', fastModel: 'claude-sonnet-5' });
    expect(anthropic.resolveModel({ model: 'claude-haiku-4-5-20251001', tier: 'fast' })).toBe(
      'claude-haiku-4-5-20251001',
    );
  });

  it('falls back to the single configured model when no fast model is set', () => {
    // Someone who sets only ANTHROPIC_MODEL gets that model everywhere, rather
    // than a surprise second model they never chose.
    const anthropic = new AnthropicProvider({ apiKey: 'k', model: 'claude-opus-5' });
    expect(anthropic.resolveModel({ tier: 'fast' })).toBe('claude-opus-5');
  });

  it('applies the same rules to the OpenAI provider', () => {
    const openai = new OpenAiProvider({ apiKey: 'k', model: 'gpt-4o', fastModel: 'gpt-4o-mini' });
    expect(openai.resolveModel({})).toBe('gpt-4o');
    expect(openai.resolveModel({ tier: 'fast' })).toBe('gpt-4o-mini');
  });

  it('prices the quality model above the fast one, so the tiers are not cosmetic', () => {
    const anthropic = new AnthropicProvider({ apiKey: 'k', model: 'claude-opus-5', fastModel: 'claude-sonnet-5' });
    expect(anthropic.estimateCost(1e6, 1e6, 'claude-opus-5')).toBeGreaterThan(
      anthropic.estimateCost(1e6, 1e6, 'claude-sonnet-5'),
    );
  });
});
