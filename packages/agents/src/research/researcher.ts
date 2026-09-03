/**
 * AGENT 3 — RESEARCHER.
 *
 * Fetches the actual source pages and extracts claims from their text. The
 * important property is that every claim carries a verbatim excerpt from a
 * fetched source: that is what makes a claim traceable, and what stops the
 * model from quietly supplementing thin sources with its training data.
 */
import { researchOutputSchema, type ResearchOutput } from '@mmos/contracts';
import type { SearchProvider, SearchResult } from '@mmos/ai';
import { Agent, type AgentContext, type AgentResult } from '../base.js';
import { PROMPTS } from '../prompts.js';

export interface ResearchInput {
  topicId: string;
  title: string;
  summary: string;
  keywords: string[];
  /** Sources already found by the trend hunter. */
  knownSources?: SearchResult[];
  minSources?: number;
}

export interface ResearchedSource {
  url: string;
  title: string;
  publisher?: string;
  publishedAt?: Date;
  excerpt: string;
  fullText?: string;
  credibility: number;
  retrievedAt: Date;
}

export interface ResearchResult {
  topicId: string;
  research: ResearchOutput;
  sources: ResearchedSource[];
}

/**
 * Rough outlet credibility. Feeds claim confidence and the fact checker's
 * corroboration counting. Deliberately coarse — it is a prior, not a verdict,
 * and a wire service agreeing with a blog still needs the blog checked.
 */
const CREDIBILITY: Array<[RegExp, number]> = [
  [/reuters\.com|apnews\.com|bloomberg\.com|ft\.com|wsj\.com|economist\.com/i, 0.95],
  [/bbc\.(co\.uk|com)|nytimes\.com|washingtonpost\.com|theguardian\.com|npr\.org/i, 0.9],
  [/cnbc\.com|forbes\.com|businessinsider\.com|techcrunch\.com|theverge\.com|arstechnica\.com/i, 0.8],
  [/wikipedia\.org/i, 0.65],
  [/medium\.com|substack\.com|blogspot\.|wordpress\./i, 0.4],
];

export function credibilityOf(url: string): number {
  for (const [pattern, score] of CREDIBILITY) if (pattern.test(url)) return score;
  return 0.55;
}

export class ResearcherAgent extends Agent<ResearchInput, ResearchResult> {
  readonly name = 'researcher';
  readonly #providers: SearchProvider[];

  constructor(ctx: AgentContext, providers: SearchProvider[]) {
    super(ctx);
    this.#providers = providers;
  }

  protected async execute(input: ResearchInput): Promise<AgentResult<ResearchResult>> {
    const minSources = input.minSources ?? 3;
    const collected = new Map<string, SearchResult>();

    for (const s of input.knownSources ?? []) collected.set(canonical(s.url), s);

    // Top up with targeted searches until we have enough independent sources.
    // Corroboration is what the fact checker counts, so one source is not enough.
    if (collected.size < minSources) {
      const queries = [input.title, ...input.keywords.slice(0, 3).map((k) => `${k} ${input.title}`)];
      for (const provider of this.#providers) {
        for (const query of queries) {
          if (collected.size >= minSources + 3) break;
          try {
            for (const r of await provider.search(query, { limit: 6 })) {
              collected.set(canonical(r.url), r);
            }
          } catch (err) {
            this.ctx.logger.warn({ err, provider: provider.name }, 'source search failed');
          }
        }
      }
    }

    const fetched = await this.#fetchAll([...collected.values()].slice(0, 8));
    if (fetched.length === 0) {
      throw new Error(`No sources could be retrieved for topic "${input.title}". Research aborted.`);
    }

    const rendered = fetched
      .map(
        (s, i) =>
          `[SOURCE ${i + 1}] ${s.title}\nURL: ${s.url}\nPublisher: ${s.publisher ?? 'unknown'}\nPublished: ${s.publishedAt?.toISOString().slice(0, 10) ?? 'unknown'}\n\n${(s.fullText ?? s.excerpt).slice(0, 6000)}`,
      )
      .join('\n\n---\n\n');

    const research = await this.ctx.orchestrator.completeStructured(
      {
        system: PROMPTS.RESEARCHER.system,
        messages: [{ role: 'user', content: PROMPTS.RESEARCHER.user(input.title, rendered) }],
        maxTokens: 8000,
        temperature: 0.2, // extraction, not invention
      },
      researchOutputSchema,
      'ResearchOutput',
      { operation: 'research', topicId: input.topicId },
    );

    // Structural guard against fabrication: drop any claim whose supporting
    // excerpt does not actually appear in the fetched text. The prompt asks for
    // verbatim quotes; this verifies it rather than trusting it.
    const corpus = fetched.map((s) => normalize(s.fullText ?? s.excerpt)).join('\n');
    const verified = research.claims.filter((claim) => {
      const excerpt = normalize(claim.supportingExcerpt);
      if (excerpt.length < 15) return false;
      const present = corpus.includes(excerpt.slice(0, 60));
      if (!present) {
        this.ctx.logger.warn(
          { claim: claim.text.slice(0, 120) },
          'dropping claim: supporting excerpt not found in any fetched source',
        );
      }
      return present;
    });

    return {
      output: { topicId: input.topicId, research: { ...research, claims: verified }, sources: fetched },
      itemsProcessed: fetched.length,
      itemsProduced: verified.length,
    };
  }

  async #fetchAll(results: SearchResult[]): Promise<ResearchedSource[]> {
    const settled = await Promise.allSettled(results.map((r) => this.#fetchOne(r)));
    return settled
      .filter((s): s is PromiseFulfilledResult<ResearchedSource | null> => s.status === 'fulfilled')
      .map((s) => s.value)
      .filter((s): s is ResearchedSource => s !== null);
  }

  async #fetchOne(result: SearchResult): Promise<ResearchedSource | null> {
    const base: ResearchedSource = {
      url: result.url,
      title: result.title,
      ...(result.publisher ? { publisher: result.publisher } : {}),
      ...(result.publishedAt ? { publishedAt: result.publishedAt } : {}),
      excerpt: result.snippet,
      credibility: credibilityOf(result.url),
      retrievedAt: new Date(),
    };

    try {
      const res = await fetch(result.url, {
        headers: { 'user-agent': 'ModernManOS/1.0 (+content research)' },
        signal: AbortSignal.timeout(15_000),
      });
      // A snippet is still usable evidence, so a failed fetch degrades rather
      // than discarding the source.
      if (!res.ok) return base;

      const contentType = res.headers.get('content-type') ?? '';
      if (!contentType.includes('text/html') && !contentType.includes('text/plain')) return base;

      const html = await res.text();
      const text = stripHtml(html);
      return text.length > 200 ? { ...base, fullText: text.slice(0, 20_000) } : base;
    } catch (err) {
      this.ctx.logger.debug({ err, url: result.url }, 'could not fetch source body; using snippet');
      return base;
    }
  }
}

function canonical(url: string): string {
  return (url.split('?')[0] ?? url).replace(/\/$/, '');
}

function normalize(text: string): string {
  return text.toLowerCase().replace(/\s+/g, ' ').trim();
}

function stripHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<nav[\s\S]*?<\/nav>/gi, ' ')
    .replace(/<footer[\s\S]*?<\/footer>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}
