/**
 * Content mix and fatigue.
 *
 * Two requirements from the brief meet here: keep the portfolio balanced so no
 * category accidentally dominates, and detect fatigue so the system stops
 * producing what the audience has already ignored.
 */
import { DEFAULT_CONTENT_MIX } from '@mmos/core';

export type CategoryMix = Record<string, number>;

export interface MixAnalysis {
  target: CategoryMix;
  actual: CategoryMix;
  /** Positive = under-served and owed more content; negative = over-served. */
  deficit: Record<string, number>;
  /** Categories ordered by need. The planner walks this list. */
  priorityOrder: string[];
}

export function analyzeMix(
  recentCategoryCounts: Record<string, number>,
  target: CategoryMix = DEFAULT_CONTENT_MIX,
): MixAnalysis {
  const total = Object.values(recentCategoryCounts).reduce((a, b) => a + b, 0);

  const actual: CategoryMix = {};
  const deficit: Record<string, number> = {};
  for (const category of Object.keys(target)) {
    const count = recentCategoryCounts[category] ?? 0;
    // With no history every category is equally owed, which is the right cold start.
    const actualPct = total > 0 ? (count / total) * 100 : 0;
    actual[category] = Number(actualPct.toFixed(2));
    deficit[category] = Number(((target[category] ?? 0) - actualPct).toFixed(2));
  }

  const priorityOrder = Object.keys(deficit).sort((a, b) => (deficit[b] ?? 0) - (deficit[a] ?? 0));
  return { target, actual, deficit, priorityOrder };
}

/**
 * Allows analytics to override the target mix, but only within bounds. An
 * unbounded feedback loop would collapse the account into a single category
 * after one good week, which is exactly the failure the brief warns about.
 */
export function adjustMixByPerformance(
  target: CategoryMix,
  categoryLift: Record<string, number>,
  maxShiftPct = 5,
): CategoryMix {
  const adjusted: CategoryMix = { ...target };
  for (const [category, lift] of Object.entries(categoryLift)) {
    const base = target[category];
    if (base === undefined) continue;
    // lift is relative to baseline: 1.0 is average, 1.5 is 50% better.
    const shift = Math.max(-maxShiftPct, Math.min(maxShiftPct, (lift - 1) * maxShiftPct));
    adjusted[category] = Math.max(0, base + shift);
  }

  // Renormalize to 100 so the result is still a valid mix.
  const sum = Object.values(adjusted).reduce((a, b) => a + b, 0);
  if (sum === 0) return target;
  for (const key of Object.keys(adjusted)) {
    adjusted[key] = Number((((adjusted[key] ?? 0) / sum) * 100).toFixed(2));
  }
  return adjusted;
}

export interface FatigueSignal {
  kind: 'CATEGORY' | 'FORMAT' | 'HOOK_ARCHETYPE' | 'TOPIC';
  key: string;
  occurrences: number;
  windowSize: number;
  sharePct: number;
  recommendation: string;
}

/**
 * Flags anything occupying more than `maxSharePct` of a recent window.
 * Repetition is the fastest way to train an audience to scroll past.
 */
export function detectFatigue(
  recent: Array<{ category?: string; format?: string; hookArchetype?: string; topicTitle?: string }>,
  maxSharePct = 40,
): FatigueSignal[] {
  const signals: FatigueSignal[] = [];
  const windowSize = recent.length;
  if (windowSize < 5) return signals; // too little history to call anything fatigue

  const dimensions: Array<[FatigueSignal['kind'], (i: (typeof recent)[number]) => string | undefined]> = [
    ['CATEGORY', (i) => i.category],
    ['FORMAT', (i) => i.format],
    ['HOOK_ARCHETYPE', (i) => i.hookArchetype],
  ];

  for (const [kind, pick] of dimensions) {
    const counts = new Map<string, number>();
    for (const item of recent) {
      const key = pick(item);
      if (key) counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    for (const [key, occurrences] of counts) {
      const sharePct = (occurrences / windowSize) * 100;
      if (sharePct > maxSharePct) {
        signals.push({
          kind,
          key,
          occurrences,
          windowSize,
          sharePct: Number(sharePct.toFixed(1)),
          recommendation: `${key} is ${sharePct.toFixed(0)}% of the last ${windowSize} posts. Diversify away from it in the next cycle.`,
        });
      }
    }
  }

  return signals.sort((a, b) => b.sharePct - a.sharePct);
}
