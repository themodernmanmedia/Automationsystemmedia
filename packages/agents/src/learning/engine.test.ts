import { describe, expect, it } from 'vitest';
import {
  adjustScoringWeights,
  computeInsights,
  MIN_SAMPLE_SIZE,
  optimalPostingHours,
  performanceScore,
  type PostPerformance,
} from './engine.js';
import { DEFAULT_SCORING_WEIGHTS } from '@mmos/core';

function post(overrides: Partial<PostPerformance> = {}): PostPerformance {
  return {
    contentPieceId: 'cp',
    category: 'BUSINESS',
    format: 'CAROUSEL',
    postedAtHour: 9,
    postedAtWeekday: 2,
    views: 10_000,
    reach: 10_000,
    likes: 100,
    comments: 10,
    shares: 10,
    saves: 10,
    avgWatchTimeSec: null,
    followsGained: 5,
    ...overrides,
  };
}

describe('performanceScore', () => {
  it('values saves and shares above likes', () => {
    const likeHeavy = performanceScore(post({ likes: 500, saves: 0, shares: 0, followsGained: 0 }))!;
    const saveHeavy = performanceScore(post({ likes: 0, saves: 200, shares: 0, followsGained: 0 }))!;
    // 200 saves at weight 3 beats 500 likes at weight 1 — the brief rejects
    // optimizing for the vanity metric.
    expect(saveHeavy).toBeGreaterThan(likeHeavy);
  });

  it('normalizes by reach so a small account is comparable to a large one', () => {
    const small = performanceScore(post({ reach: 1_000, likes: 10, comments: 1, shares: 1, saves: 1, followsGained: 0 }))!;
    const large = performanceScore(post({ reach: 100_000, likes: 1_000, comments: 100, shares: 100, saves: 100, followsGained: 0 }))!;
    expect(small).toBeCloseTo(large, 3);
  });

  it('returns null when there is no reach denominator', () => {
    expect(performanceScore(post({ reach: null, views: null }))).toBeNull();
  });
});

describe('computeInsights', () => {
  it('identifies an outperforming category', () => {
    const posts = [
      ...Array.from({ length: 6 }, () => post({ category: 'AI', saves: 100 })),
      ...Array.from({ length: 6 }, () => post({ category: 'LIFESTYLE', saves: 2 })),
    ];
    const { insights } = computeInsights(posts);
    const ai = insights.find((i) => i.dimension === 'category' && i.key === 'AI')!;
    const lifestyle = insights.find((i) => i.dimension === 'category' && i.key === 'LIFESTYLE')!;
    expect(ai.liftVsBaseline).toBeGreaterThan(1);
    expect(lifestyle.liftVsBaseline).toBeLessThan(1);
  });

  it('gives zero confidence below the sample-size floor', () => {
    const posts = Array.from({ length: MIN_SAMPLE_SIZE - 1 }, () => post({ category: 'AI' }));
    const { insights } = computeInsights(posts);
    expect(insights.find((i) => i.key === 'AI')!.confidence).toBe(0);
  });

  it('returns nothing when no post has usable analytics', () => {
    const { insights, baseline } = computeInsights([post({ reach: null, views: null })]);
    expect(insights).toEqual([]);
    expect(baseline).toBe(0);
  });
});

describe('adjustScoringWeights', () => {
  it('never moves a weight by more than the configured step', () => {
    const posts = [
      ...Array.from({ length: 20 }, () => post({ category: 'AI', saves: 500 })),
      ...Array.from({ length: 20 }, () => post({ category: 'SPORTS', saves: 1 })),
      ...Array.from({ length: 20 }, () => post({ category: 'LUXURY', saves: 50 })),
    ];
    const { insights } = computeInsights(posts);
    const maxStep = 0.02;
    const { weights, adjustments } = adjustScoringWeights(DEFAULT_SCORING_WEIGHTS, insights, maxStep);

    expect(adjustments.length).toBeGreaterThan(0);
    for (const key of Object.keys(DEFAULT_SCORING_WEIGHTS)) {
      const before = DEFAULT_SCORING_WEIGHTS[key]!;
      const after = weights[key]!;
      // Renormalization shifts everything slightly, so allow a small margin
      // above maxStep — the guarantee is "bounded", not "frozen".
      expect(Math.abs(after - before)).toBeLessThan(maxStep + 0.01);
    }
  });

  it('leaves weights a valid normalized distribution', () => {
    const { insights } = computeInsights(Array.from({ length: 20 }, () => post()));
    const { weights } = adjustScoringWeights(DEFAULT_SCORING_WEIGHTS, insights);
    const sum = Object.values(weights).reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1, 2);
  });

  it('makes no adjustment from an underpowered sample', () => {
    const { insights } = computeInsights(Array.from({ length: 3 }, () => post({ category: 'AI', saves: 999 })));
    const { adjustments } = adjustScoringWeights(DEFAULT_SCORING_WEIGHTS, insights);
    expect(adjustments).toEqual([]);
  });
});

describe('optimalPostingHours', () => {
  it('ranks hours by measured performance', () => {
    const posts = [
      ...Array.from({ length: 4 }, () => post({ postedAtHour: 18, saves: 200 })),
      ...Array.from({ length: 4 }, () => post({ postedAtHour: 3, saves: 1 })),
    ];
    const hours = optimalPostingHours(posts, 2);
    expect(hours[0]!.hour).toBe(18);
  });

  it('ignores hours with too little data rather than guessing', () => {
    const posts = [post({ postedAtHour: 7, saves: 9999 }), post({ postedAtHour: 8, saves: 1 })];
    expect(optimalPostingHours(posts)).toEqual([]);
  });
});
