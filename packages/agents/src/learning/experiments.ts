/**
 * A/B experiments.
 *
 * The brief's constraint is the important one: do not change several variables
 * at once, because the result is uninterpretable. An experiment here therefore
 * has exactly one variable, and `startExperiment` refuses anything else.
 *
 * The statistics are deliberately conservative. A social account produces tens
 * of posts, not thousands, so the default failure mode is calling a winner from
 * noise. Two guards apply: a minimum sample per arm, and a two-sided Welch's
 * t-test at 95%. When the test cannot separate the arms, the verdict is
 * INCONCLUSIVE — which is a real result and is recorded as one, rather than
 * quietly promoting whichever arm happened to lead.
 */
import { fingerprint, ValidationError } from '@mmos/core';

export const EXPERIMENT_VARIABLES = [
  'hook',
  'cover',
  'caption',
  'cta',
  'visual_style',
  'posting_time',
  'length',
] as const;

export type ExperimentVariable = (typeof EXPERIMENT_VARIABLES)[number];

export interface ExperimentVariant {
  key: string;
  description: string;
}

export interface ExperimentDefinition {
  name: string;
  hypothesis: string;
  variable: ExperimentVariable;
  variants: ExperimentVariant[];
  minSampleSize?: number;
}

/**
 * Validates a proposed experiment.
 *
 * Enforces the single-variable rule and a floor on sample size, since an
 * experiment that can conclude from three posts per arm is not an experiment.
 */
export function validateExperiment(definition: ExperimentDefinition): void {
  if (!EXPERIMENT_VARIABLES.includes(definition.variable)) {
    throw new ValidationError(
      `"${definition.variable}" is not a testable variable. One of: ${EXPERIMENT_VARIABLES.join(', ')}.`,
    );
  }
  if (definition.variants.length < 2) {
    throw new ValidationError('An experiment needs at least two variants to compare.');
  }
  // More arms split a small sample further; four is already thin at these volumes.
  if (definition.variants.length > 4) {
    throw new ValidationError(
      `${definition.variants.length} variants would split the sample too thinly. Use at most 4.`,
    );
  }
  const keys = definition.variants.map((v) => v.key);
  if (new Set(keys).size !== keys.length) {
    throw new ValidationError('Variant keys must be unique.');
  }
  if ((definition.minSampleSize ?? 10) < 5) {
    throw new ValidationError('Minimum sample size must be at least 5 posts per variant.');
  }
}

/**
 * Assigns a content piece to an arm.
 *
 * Deterministic on the piece id, so a retried or regenerated piece lands in the
 * same arm every time. Random assignment would let a retry silently move a
 * piece between arms and corrupt the comparison.
 */
export function assignVariant(
  experimentId: string,
  contentPieceId: string,
  variants: ExperimentVariant[],
): string {
  if (variants.length === 0) throw new ValidationError('No variants to assign');
  const hash = fingerprint(`${experimentId}:${contentPieceId}`);
  // First 8 hex chars is plenty of entropy and stays inside Number precision.
  const bucket = Number.parseInt(hash.slice(0, 8), 16) % variants.length;
  return variants[bucket]!.key;
}

/* ------------------------------ statistics ------------------------------ */

export interface VariantStats {
  key: string;
  sampleSize: number;
  mean: number;
  stdDev: number;
  /** Standard error of the mean; the basis for the comparison below. */
  standardError: number;
}

export function summarize(key: string, values: number[]): VariantStats {
  const n = values.length;
  if (n === 0) return { key, sampleSize: 0, mean: 0, stdDev: 0, standardError: 0 };

  const mean = values.reduce((a, b) => a + b, 0) / n;
  // Sample variance (n-1): these are samples of possible posts, not a population.
  const variance = n > 1 ? values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (n - 1) : 0;
  const stdDev = Math.sqrt(variance);

  return {
    key,
    sampleSize: n,
    mean: Number(mean.toFixed(4)),
    stdDev: Number(stdDev.toFixed(4)),
    standardError: n > 0 ? Number((stdDev / Math.sqrt(n)).toFixed(4)) : 0,
  };
}

/**
 * Two-sided critical t values at 95%, by degrees of freedom.
 *
 * A table rather than an incomplete-beta implementation: the sample sizes here
 * are small and bounded, so a lookup covers the real range exactly and is far
 * easier to verify than a numerical approximation would be.
 */
const T_CRITICAL_95: Array<[df: number, t: number]> = [
  [1, 12.706], [2, 4.303], [3, 3.182], [4, 2.776], [5, 2.571],
  [6, 2.447], [7, 2.365], [8, 2.306], [9, 2.262], [10, 2.228],
  [12, 2.179], [14, 2.145], [16, 2.120], [18, 2.101], [20, 2.086],
  [25, 2.060], [30, 2.042], [40, 2.021], [60, 2.000], [120, 1.980],
];

export function criticalT95(df: number): number {
  if (df < 1) return Number.POSITIVE_INFINITY;
  for (const [threshold, value] of T_CRITICAL_95) {
    if (df <= threshold) return value;
  }
  return 1.96; // normal approximation for large df
}

export interface Comparison {
  /** The arm with the higher mean. */
  leader: string;
  challenger: string;
  difference: number;
  /** Relative lift over the challenger, e.g. 1.3 means 30% better. */
  lift: number;
  tStatistic: number;
  degreesOfFreedom: number;
  /** True when the 95% two-sided test separates the arms. */
  significant: boolean;
}

/**
 * Welch's t-test.
 *
 * Welch rather than Student's because the arms will not have equal variance —
 * a bolder hook variant produces more spread as well as a different mean, and
 * assuming equal variance would overstate confidence.
 */
export function compare(a: VariantStats, b: VariantStats): Comparison | null {
  if (a.sampleSize < 2 || b.sampleSize < 2) return null;

  const [leader, challenger] = a.mean >= b.mean ? [a, b] : [b, a];

  const varA = leader.stdDev ** 2 / leader.sampleSize;
  const varB = challenger.stdDev ** 2 / challenger.sampleSize;
  const denominator = Math.sqrt(varA + varB);

  // Zero spread in both arms: identical observations, nothing to test.
  if (denominator === 0) {
    return {
      leader: leader.key,
      challenger: challenger.key,
      difference: Number((leader.mean - challenger.mean).toFixed(4)),
      lift: challenger.mean === 0 ? 0 : Number((leader.mean / challenger.mean).toFixed(3)),
      tStatistic: 0,
      degreesOfFreedom: 0,
      significant: false,
    };
  }

  const tStatistic = (leader.mean - challenger.mean) / denominator;

  // Welch–Satterthwaite degrees of freedom.
  const df =
    (varA + varB) ** 2 /
    (varA ** 2 / (leader.sampleSize - 1) + varB ** 2 / (challenger.sampleSize - 1));

  return {
    leader: leader.key,
    challenger: challenger.key,
    difference: Number((leader.mean - challenger.mean).toFixed(4)),
    lift: challenger.mean === 0 ? 0 : Number((leader.mean / challenger.mean).toFixed(3)),
    tStatistic: Number(tStatistic.toFixed(4)),
    degreesOfFreedom: Number(df.toFixed(2)),
    significant: Math.abs(tStatistic) > criticalT95(df),
  };
}

export type ExperimentVerdict = 'COLLECTING' | 'WINNER' | 'INCONCLUSIVE';

export interface ExperimentAnalysis {
  verdict: ExperimentVerdict;
  variants: VariantStats[];
  comparison: Comparison | null;
  winner?: string;
  conclusion: string;
  /** Posts still needed per arm before the experiment can conclude. */
  shortfall: Record<string, number>;
}

/**
 * Analyses an experiment's observations.
 *
 * With more than two arms, the leader is compared against the best of the rest.
 * That is the decision that matters — "should we adopt the leader" — and it
 * avoids the multiple-comparison inflation of testing every pair.
 */
export function analyzeExperiment(
  observations: Record<string, number[]>,
  variants: ExperimentVariant[],
  minSampleSize: number,
): ExperimentAnalysis {
  const stats = variants.map((variant) => summarize(variant.key, observations[variant.key] ?? []));

  const shortfall: Record<string, number> = {};
  for (const stat of stats) {
    shortfall[stat.key] = Math.max(0, minSampleSize - stat.sampleSize);
  }

  const underpowered = stats.filter((s) => s.sampleSize < minSampleSize);
  if (underpowered.length > 0) {
    const needed = underpowered.map((s) => `${s.key} needs ${minSampleSize - s.sampleSize} more`);
    return {
      verdict: 'COLLECTING',
      variants: stats,
      comparison: null,
      conclusion: `Still collecting: ${needed.join(', ')}.`,
      shortfall,
    };
  }

  const ranked = [...stats].sort((a, b) => b.mean - a.mean);
  const [best, runnerUp] = ranked as [VariantStats, VariantStats];
  const comparison = compare(best, runnerUp);

  if (!comparison || !comparison.significant) {
    return {
      verdict: 'INCONCLUSIVE',
      variants: stats,
      comparison,
      conclusion:
        `No variant separated from the others at 95% confidence. ` +
        `${best.key} led with a mean of ${best.mean} against ${runnerUp.mean}, but the difference ` +
        `is within the noise at this sample size. Keep the current approach, or rerun with more posts.`,
      shortfall,
    };
  }

  return {
    verdict: 'WINNER',
    variants: stats,
    comparison,
    winner: comparison.leader,
    conclusion:
      `${comparison.leader} outperformed ${comparison.challenger} by ` +
      `${((comparison.lift - 1) * 100).toFixed(0)}% (means ${best.mean} vs ${runnerUp.mean}, ` +
      `t=${comparison.tStatistic}, df=${comparison.degreesOfFreedom}), which separates at 95% confidence.`,
    shortfall,
  };
}
