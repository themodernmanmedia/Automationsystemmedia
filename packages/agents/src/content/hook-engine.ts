/**
 * AGENT 6 — HOOK ENGINE.
 *
 * Generates many hooks, scores each, and selects the strongest. The scoring
 * weights favor specificity and truthfulness, and a hook that scores low on
 * truthfulness is rejected outright regardless of how well it performs
 * elsewhere — the brief forbids misleading clickbait, so a high curiosity score
 * must never be able to buy its way past that.
 */
import { hookSetSchema } from '@mmos/contracts';
import { Agent, type AgentContext, type AgentResult } from '../base.js';
import { PROMPTS } from '../prompts.js';
import { similarity, SIMILARITY_THRESHOLDS } from '../research/dedupe.js';

export interface HookInput {
  topicId: string;
  title: string;
  researchSummary: string;
  verifiedClaims: string[];
  count?: number;
  /** Previously used hooks, to keep the account from repeating itself. */
  previousHooks?: string[];
  /** Archetypes the learning engine has seen underperform. */
  weakArchetypes?: string[];
}

export interface ScoredHook {
  text: string;
  archetype: string;
  scores: Record<string, number>;
  composite: number;
  rejected?: string;
}

export interface HookResult {
  selected: ScoredHook;
  alternatives: ScoredHook[];
  rejected: ScoredHook[];
}

/** Truthfulness is a gate, not a weight. Below this, the hook is discarded. */
const TRUTHFULNESS_FLOOR = 70;

const HOOK_WEIGHTS: Record<string, number> = {
  curiosity: 0.22,
  scrollStopping: 0.22,
  specificity: 0.2, // the difference between a real hook and a slogan
  clarity: 0.15,
  emotionalImpact: 0.11,
  brandFit: 0.1,
};

export class HookEngineAgent extends Agent<HookInput, HookResult> {
  readonly name = 'hook_engine';

  constructor(ctx: AgentContext) {
    super(ctx);
  }

  protected async execute(input: HookInput): Promise<AgentResult<HookResult>> {
    const count = input.count ?? 20;
    const avoidNote = input.weakArchetypes?.length
      ? `\n\nThese archetypes have underperformed for this brand recently; avoid or improve on them: ${input.weakArchetypes.join(', ')}.`
      : '';

    const research = [
      `Summary: ${input.researchSummary}`,
      `Verified facts you may use:\n${input.verifiedClaims.map((c) => `  - ${c}`).join('\n')}`,
      avoidNote,
    ].join('\n\n');

    const result = await this.ctx.orchestrator.completeStructured(
      {
        system: PROMPTS.HOOK_ENGINE.system,
        messages: [{ role: 'user', content: PROMPTS.HOOK_ENGINE.user(input.title, research, count) }],
        maxTokens: 6000,
        temperature: 0.9, // this is the one place we want real variance
      },
      hookSetSchema,
      'HookSet',
      { operation: 'hook_generation', topicId: input.topicId },
    );

    const evaluated: ScoredHook[] = [];
    const rejected: ScoredHook[] = [];

    for (const hook of result.hooks) {
      const scored: ScoredHook = {
        text: hook.text,
        archetype: hook.archetype,
        scores: hook.scores,
        composite: weightedScore(hook.scores),
      };

      if (hook.scores.truthfulness < TRUTHFULNESS_FLOOR) {
        rejected.push({
          ...scored,
          rejected: `Truthfulness ${hook.scores.truthfulness} is below the ${TRUTHFULNESS_FLOOR} floor. Misleading hooks are never used.`,
        });
        continue;
      }

      const clash = (input.previousHooks ?? []).find(
        (prev) => similarity(hook.text, prev) >= SIMILARITY_THRESHOLDS.hook,
      );
      if (clash) {
        rejected.push({ ...scored, rejected: `Too similar to a previously used hook: "${clash}"` });
        continue;
      }

      evaluated.push(scored);
    }

    if (evaluated.length === 0) {
      throw new Error(
        `Every generated hook was rejected (${rejected.length} candidates). The topic may be too thin or too repetitive to publish.`,
      );
    }

    evaluated.sort((a, b) => b.composite - a.composite);
    const [selected, ...alternatives] = evaluated as [ScoredHook, ...ScoredHook[]];

    return {
      output: { selected, alternatives: alternatives.slice(0, 5), rejected },
      itemsProcessed: result.hooks.length,
      itemsProduced: evaluated.length,
    };
  }
}

function weightedScore(scores: Record<string, number>): number {
  let total = 0;
  let weight = 0;
  for (const [key, w] of Object.entries(HOOK_WEIGHTS)) {
    const value = scores[key];
    if (value === undefined) continue;
    total += value * w;
    weight += w;
  }
  return weight > 0 ? Number((total / weight).toFixed(2)) : 0;
}
