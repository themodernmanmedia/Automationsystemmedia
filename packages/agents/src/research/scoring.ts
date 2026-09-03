/**
 * Topic scoring.
 *
 * The LLM supplies per-dimension judgments; this module combines them
 * deterministically. Keeping the arithmetic out of the model matters: weights
 * are configurable and are adjusted by the learning engine, and a weighted sum
 * computed in code is reproducible, auditable, and free.
 */
import { DEFAULT_SCORING_WEIGHTS } from '@mmos/core';
import { SCORING_DIMENSIONS } from '@mmos/contracts';

export type ScoringDimension = (typeof SCORING_DIMENSIONS)[number];
export type DimensionScores = Record<ScoringDimension, number>;
export type ScoringWeights = Record<string, number>;

export interface CompositeScoreResult {
  composite: number;
  weighted: Record<string, number>;
  /** Dimensions the weights omitted, so a misconfiguration is visible. */
  missingDimensions: string[];
}

/**
 * Weighted mean on a 0-100 scale. Weights are normalized rather than assumed to
 * sum to 1, so a partial or hand-edited weight map still produces a comparable
 * score instead of a silently deflated one.
 */
export function computeCompositeScore(
  scores: Partial<DimensionScores>,
  weights: ScoringWeights = DEFAULT_SCORING_WEIGHTS,
): CompositeScoreResult {
  const weighted: Record<string, number> = {};
  const missingDimensions: string[] = [];
  let totalWeight = 0;
  let accumulated = 0;

  for (const dimension of SCORING_DIMENSIONS) {
    const value = scores[dimension];
    const weight = weights[dimension];
    if (value === undefined) {
      missingDimensions.push(dimension);
      continue;
    }
    if (weight === undefined || weight <= 0) continue;
    const clamped = Math.max(0, Math.min(100, value));
    weighted[dimension] = clamped * weight;
    accumulated += clamped * weight;
    totalWeight += weight;
  }

  return {
    composite: totalWeight > 0 ? Number((accumulated / totalWeight).toFixed(2)) : 0,
    weighted,
    missingDimensions,
  };
}

export interface ViralityFeatures {
  topicScore: number;
  hookScore: number;
  formatScore: number;
  categoryHistoricalScore: number;
  visualScore: number;
  timeliness: number;
  audienceMatch: number;
}

/**
 * A RANKING score, not a prediction.
 *
 * The brief is explicit that this must not be presented as a guarantee of
 * virality, and the UI labels it accordingly. Its only job is to order a queue
 * so that the strongest candidate goes out first.
 */
export function computeViralPotential(features: Partial<ViralityFeatures>): number {
  const weights: Record<keyof ViralityFeatures, number> = {
    topicScore: 0.25,
    hookScore: 0.25, // the hook decides whether anything else is ever seen
    formatScore: 0.1,
    categoryHistoricalScore: 0.15, // measured performance, not a guess
    visualScore: 0.1,
    timeliness: 0.1,
    audienceMatch: 0.05,
  };

  let total = 0;
  let used = 0;
  for (const [key, weight] of Object.entries(weights) as Array<[keyof ViralityFeatures, number]>) {
    const value = features[key];
    if (value === undefined) continue;
    total += Math.max(0, Math.min(100, value)) * weight;
    used += weight;
  }
  return used > 0 ? Number((total / used).toFixed(2)) : 0;
}

/**
 * Timeliness decay.
 *
 * Breaking news is worth far more in hour one than in hour twenty, and an
 * evergreen topic barely decays at all. Modeling this stops a queue from
 * publishing yesterday's urgent story tomorrow.
 */
export function timelinessScore(
  discoveredAt: Date,
  isBreakingNews: boolean,
  now: Date = new Date(),
): number {
  const ageHours = (now.getTime() - discoveredAt.getTime()) / 3_600_000;
  if (ageHours < 0) return 100;
  // Half-life: 6h for breaking news, 14 days for evergreen.
  const halfLifeHours = isBreakingNews ? 6 : 24 * 14;
  return Number((100 * Math.pow(0.5, ageHours / halfLifeHours)).toFixed(2));
}
