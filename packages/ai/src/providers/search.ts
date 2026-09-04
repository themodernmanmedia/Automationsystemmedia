/**
 * Research and trend-discovery sources.
 *
 * Since no platform offers a legitimate commercial trend feed (see
 * docs/API_LIMITATIONS.md §5), discovery runs on news, RSS, and web search.
 * RSS is deliberately first-class: it needs no API key, so the system does
 * something genuinely useful the moment it boots.
 */
import { AiError, ProviderNotConfiguredError, withRetry } from '@mmos/core';
import type { SearchProvider, SearchResult } from '../types.js';

export class BraveSearchProvider implements SearchProvider {
  readonly name = 'brave';
  readonly #apiKey: string;
  readonly #baseUrl: string;

  constructor(config: { apiKey?: string; baseUrl?: string }) {
    if (!config.apiKey) throw new ProviderNotConfiguredError('Brave search', ['BRAVE_SEARCH_API_KEY']);
    this.#apiKey = config.apiKey;
    this.#baseUrl = config.baseUrl ?? 'https://api.search.brave.com/res/v1/web/search';
  }

  async search(query: string, options: { limit?: number; freshness?: 'day' | 'week' | 'month' } = {}): Promise<SearchResult[]> {
    const url = new URL(this.#baseUrl);
    url.searchParams.set('q', query);
    url.searchParams.set('count', String(options.limit ?? 10));
    if (options.freshness) {
      url.searchParams.set('freshness', { day: 'pd', week: 'pw', month: 'pm' }[options.freshness]);
    }

    const body = await withRetry(
      async () => {
        const res = await fetch(url, {
          headers: { accept: 'application/json', 'x-subscription-token': this.#apiKey },
        });
        if (!res.ok) {
          throw new AiError(`Brave search returned HTTP ${res.status}`, {
            retryable: res.status === 429 || res.status >= 500,
          });
        }
        return (await res.json()) as {
          web?: { results?: Array<{ title: string; url: string; description?: string; age?: string; profile?: { name?: string } }> };
        };
      },
      { maxAttempts: 3 },
    );

    return (body.web?.results ?? []).map((r) => ({
      title: r.title,
      url: r.url,
      snippet: r.description ?? '',
      ...(r.profile?.name ? { publisher: r.profile.name } : {}),
    }));
  }
}

export class TavilySearchProvider implements SearchProvider {
  readonly name = 'tavily';
  readonly #apiKey: string;
  readonly #baseUrl: string;

  constructor(config: { apiKey?: string; baseUrl?: string }) {
    if (!config.apiKey) throw new ProviderNotConfiguredError('Tavily search', ['TAVILY_API_KEY']);
    this.#apiKey = config.apiKey;
    this.#baseUrl = config.baseUrl ?? 'https://api.tavily.com/search';
  }

  async search(query: string, options: { limit?: number } = {}): Promise<SearchResult[]> {
    const body = await withRetry(
      async () => {
        const res = await fetch(this.#baseUrl, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            api_key: this.#apiKey,
            query,
            max_results: options.limit ?? 10,
            search_depth: 'advanced',
            include_raw_content: true,
          }),
        });
        if (!res.ok) {
          throw new AiError(`Tavily returned HTTP ${res.status}`, {
            retryable: res.status === 429 || res.status >= 500,
          });
        }
        return (await res.json()) as {
          results?: Array<{ title: string; url: string; content?: string; published_date?: string }>;
        };
      },
      { maxAttempts: 3 },
    );

    return (body.results ?? []).map((r) => ({
      title: r.title,
      url: r.url,
      snippet: r.content ?? '',
      ...(r.published_date ? { publishedAt: new Date(r.published_date) } : {}),
    }));
  }
}

/**
 * RSS aggregator.
 *
 * Parsed with a targeted regex rather than an XML library: feeds are a small,
 * well-known shape, and this keeps a zero-key path to real trend data with no
 * extra dependency. A malformed feed is skipped, never fatal — one broken
 * publisher must not stop the whole scan.
 */
export class RssSearchProvider implements SearchProvider {
  readonly name = 'rss';
  readonly #feeds: string[];

  constructor(config: { feeds: string[] }) {
    this.#feeds = config.feeds;
  }

  async search(query: string, options: { limit?: number } = {}): Promise<SearchResult[]> {
    const settled = await Promise.allSettled(this.#feeds.map((f) => this.#fetchFeed(f)));
    const items = settled.flatMap((r) => (r.status === 'fulfilled' ? r.value : []));

    // An empty query means "everything recent" — that is the trend-scan case.
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    const matched = terms.length
      ? items.filter((i) => {
          const hay = `${i.title} ${i.snippet}`.toLowerCase();
          return terms.some((t) => hay.includes(t));
        })
      : items;

    return matched
      .sort((a, b) => (b.publishedAt?.getTime() ?? 0) - (a.publishedAt?.getTime() ?? 0))
      .slice(0, options.limit ?? 25);
  }

  /** All recent items across every feed, for an untargeted trend scan. */
  async fetchLatest(limit = 50): Promise<SearchResult[]> {
    return this.search('', { limit });
  }

  async #fetchFeed(feedUrl: string): Promise<SearchResult[]> {
    const res = await fetch(feedUrl, {
      headers: { 'user-agent': 'ModernManOS/1.0 (+content research)' },
      signal: AbortSignal.timeout(15_000),
    });
    if (!res.ok) return [];
    const xml = await res.text();

    const publisher = hostOf(feedUrl);
    const entries = [...xml.matchAll(/<(item|entry)\b[\s\S]*?<\/\1>/g)].map((m) => m[0]);

    return entries
      .map((entry): SearchResult | null => {
        const title = decodeXml(tag(entry, 'title'));
        const link = tag(entry, 'link') || attr(entry, 'link', 'href');
        // The feed chooses this value, so reject anything that is not an
        // ordinary web link before it is stored and later fetched. The full
        // address check happens at fetch time; this only stops the obvious
        // schemes from ever entering the source table.
        if (!title || !link || !isWebLink(link.trim())) return null;
        const dateText = tag(entry, 'pubDate') || tag(entry, 'published') || tag(entry, 'updated');
        const parsed = dateText ? new Date(dateText) : undefined;
        return {
          title,
          url: link.trim(),
          snippet: decodeXml(tag(entry, 'description') || tag(entry, 'summary')).slice(0, 600),
          publisher,
          ...(parsed && !Number.isNaN(parsed.getTime()) ? { publishedAt: parsed } : {}),
        };
      })
      .filter((r): r is SearchResult => r !== null);
  }
}

/** True only for an absolute http(s) URL with no embedded credentials. */
function isWebLink(value: string): boolean {
  try {
    const u = new URL(value);
    return (u.protocol === 'http:' || u.protocol === 'https:') && !u.username && !u.password;
  } catch {
    return false;
  }
}

function tag(xml: string, name: string): string {
  const m = xml.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`));
  return stripCdata(m?.[1] ?? '').trim();
}

function attr(xml: string, tagName: string, attrName: string): string {
  const m = xml.match(new RegExp(`<${tagName}[^>]*\\b${attrName}=["']([^"']+)["']`));
  return m?.[1] ?? '';
}

function stripCdata(s: string): string {
  return s.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1');
}

function decodeXml(s: string): string {
  return s
    .replace(/<[^>]+>/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;|&apos;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
    .trim();
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return 'unknown';
  }
}
