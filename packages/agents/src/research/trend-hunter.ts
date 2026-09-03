/**
 * AGENT 1 — TREND HUNTER.
 *
 * Pulls real items from configured sources, then asks the model to pick the
 * strongest candidates. The model never invents a story: it only selects from
 * and summarizes what was actually retrieved, which is what keeps discovery
 * grounded in something that happened.
 */
import { z } from 'zod';
import type { SearchProvider, SearchResult } from '@mmos/ai';
import { discoveredTopicSchema, type DiscoveredTopic } from '@mmos/contracts';
import { Agent, type AgentContext, type AgentResult } from '../base.js';
import { PROMPTS } from '../prompts.js';
import { contentHash, isDuplicate, SIMILARITY_THRESHOLDS } from './dedupe.js';

const trendOutputSchema = z.object({ topics: z.array(discoveredTopicSchema).max(25) });

export interface TrendHunterInput {
  /** Search queries per category; empty means "sweep the RSS feeds". */
  queries?: string[];
  maxTopics?: number;
  /** Existing topic titles, so the agent does not rediscover known stories. */
  existingTopics?: Array<{ id: string; text: string }>;
}

export interface DiscoveredTopicRecord extends DiscoveredTopic {
  discoverySource: string;
  discoveryUrl?: string;
  contentHash: string;
  sources: SearchResult[];
}

export class TrendHunterAgent extends Agent<TrendHunterInput, DiscoveredTopicRecord[]> {
  readonly name = 'trend_hunter';
  readonly #providers: SearchProvider[];

  constructor(ctx: AgentContext, providers: SearchProvider[]) {
    super(ctx);
    this.#providers = providers;
  }

  protected async execute(input: TrendHunterInput): Promise<AgentResult<DiscoveredTopicRecord[]>> {
    const queries = input.queries ?? [''];
    const maxTopics = input.maxTopics ?? 10;

    // One provider failing must not abort the scan — a dead RSS feed is normal.
    const settled = await Promise.allSettled(
      this.#providers.flatMap((p) =>
        queries.map((q) => p.search(q, { limit: 15, freshness: 'day' }).catch((err) => {
          this.ctx.logger.warn({ err, provider: p.name, query: q }, 'search provider failed');
          return [] as SearchResult[];
        })),
      ),
    );

    const items = settled
      .flatMap((r) => (r.status === 'fulfilled' ? r.value : []))
      .filter((item) => item.title && item.url);

    const unique = dedupeByUrl(items).slice(0, 60);
    if (unique.length === 0) {
      this.ctx.logger.warn('trend hunter retrieved no items from any source');
      return { output: [], itemsProcessed: 0, itemsProduced: 0 };
    }

    const rendered = unique
      .map((item, i) => {
        const when = item.publishedAt ? ` (${item.publishedAt.toISOString().slice(0, 10)})` : '';
        return `[${i + 1}] ${item.title}${when}\n    source: ${item.publisher ?? hostOf(item.url)}\n    ${item.snippet.slice(0, 400)}`;
      })
      .join('\n\n');

    const result = await this.ctx.orchestrator.completeStructured(
      {
        system: PROMPTS.TREND_HUNTER.system,
        messages: [{ role: 'user', content: PROMPTS.TREND_HUNTER.user(rendered) }],
        maxTokens: 6000,
        temperature: 0.6,
      },
      trendOutputSchema,
      'DiscoveredTopics',
      { operation: 'trend_discovery' },
    );

    // Dedupe against what we already know, then against each other, so one scan
    // cannot produce three variants of the same story.
    const existing = [...(input.existingTopics ?? [])];
    const output: DiscoveredTopicRecord[] = [];

    for (const topic of result.topics) {
      const text = `${topic.title} ${topic.summary}`;
      if (isDuplicate(text, existing, SIMILARITY_THRESHOLDS.topic)) {
        this.ctx.logger.debug({ title: topic.title }, 'skipping duplicate topic');
        continue;
      }
      const matched = matchSources(topic, unique);
      output.push({
        ...topic,
        discoverySource: this.#providers[0]?.name ?? 'search',
        ...(matched[0]?.url ? { discoveryUrl: matched[0].url } : {}),
        contentHash: contentHash(text),
        sources: matched,
      });
      existing.push({ id: `new-${output.length}`, text });
      if (output.length >= maxTopics) break;
    }

    return { output, itemsProcessed: unique.length, itemsProduced: output.length };
  }
}

function dedupeByUrl(items: SearchResult[]): SearchResult[] {
  const seen = new Set<string>();
  return items.filter((i) => {
    const key = i.url.split('?')[0] ?? i.url;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Ties a topic back to the retrieved items it came from, so the research agent
 * starts from real URLs rather than re-searching. Matching is by keyword and
 * entity overlap against title and snippet.
 */
function matchSources(topic: DiscoveredTopic, items: SearchResult[]): SearchResult[] {
  const terms = [...topic.keywords, ...topic.entities, ...topic.title.split(/\s+/)]
    .map((t) => t.toLowerCase())
    .filter((t) => t.length > 3);

  return items
    .map((item) => {
      const hay = `${item.title} ${item.snippet}`.toLowerCase();
      return { item, score: terms.filter((t) => hay.includes(t)).length };
    })
    .filter((m) => m.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map((m) => m.item);
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return 'unknown';
  }
}
