import { describe, expect, it } from 'vitest';
import { computeCompositeScore, computeViralPotential, timelinessScore } from './scoring.js';
import { DEFAULT_SCORING_WEIGHTS } from '@mmos/core';

const full = {
  CURRENT_INTEREST: 80, AUDIENCE_FIT: 90, CURIOSITY: 70, SHAREABILITY: 60,
  SAVEABILITY: 75, COMMENT_POTENTIAL: 50, VISUAL_POTENTIAL: 85, EMOTIONAL_IMPACT: 65,
  NOVELTY: 70, TIMELINESS: 95, FOLLOW_POTENTIAL: 55, BRAND_FIT: 88,
};

describe('computeCompositeScore', () => {
  it('produces a weighted mean inside the input range', () => {
    const { composite } = computeCompositeScore(full, DEFAULT_SCORING_WEIGHTS);
    expect(composite).toBeGreaterThan(50);
    expect(composite).toBeLessThan(90);
  });

  it('returns the same value for a uniform input regardless of weights', () => {
    const uniform = Object.fromEntries(Object.keys(full).map((k) => [k, 70])) as typeof full;
    expect(computeCompositeScore(uniform).composite).toBeCloseTo(70, 1);
  });

  it('normalizes partial weights instead of deflating the score', () => {
    // Only two dimensions weighted; the result should reflect those two, not be
    // dragged toward zero by the missing weight mass.
    const { composite } = computeCompositeScore(full, { AUDIENCE_FIT: 0.5, BRAND_FIT: 0.5 });
    expect(composite).toBeCloseTo(89, 0);
  });

  it('reports dimensions the caller failed to supply', () => {
    const { missingDimensions } = computeCompositeScore({ AUDIENCE_FIT: 80 });
    expect(missingDimensions).toContain('BRAND_FIT');
    expect(missingDimensions).not.toContain('AUDIENCE_FIT');
  });

  it('clamps out-of-range scores rather than propagating them', () => {
    const { composite } = computeCompositeScore({ AUDIENCE_FIT: 500 }, { AUDIENCE_FIT: 1 });
    expect(composite).toBe(100);
  });
});

describe('timelinessScore', () => {
  it('decays breaking news fast', () => {
    const now = new Date('2026-01-01T12:00:00Z');
    const fresh = timelinessScore(new Date('2026-01-01T11:00:00Z'), true, now);
    const stale = timelinessScore(new Date('2025-12-31T12:00:00Z'), true, now);
    expect(fresh).toBeGreaterThan(85);
    expect(stale).toBeLessThan(10); // 24h on a 6h half-life
  });

  it('barely decays evergreen topics over the same period', () => {
    const now = new Date('2026-01-01T12:00:00Z');
    const evergreen = timelinessScore(new Date('2025-12-31T12:00:00Z'), false, now);
    expect(evergreen).toBeGreaterThan(85);
  });

  it('is exactly 50 at one half-life', () => {
    const now = new Date('2026-01-01T12:00:00Z');
    expect(timelinessScore(new Date('2026-01-01T06:00:00Z'), true, now)).toBeCloseTo(50, 0);
  });
});

describe('computeViralPotential', () => {
  it('weights hook and topic scores most heavily', () => {
    const strongHook = computeViralPotential({ topicScore: 50, hookScore: 95, formatScore: 50 });
    const weakHook = computeViralPotential({ topicScore: 50, hookScore: 20, formatScore: 50 });
    expect(strongHook).toBeGreaterThan(weakHook + 15);
  });

  it('handles a partial feature set without collapsing to zero', () => {
    expect(computeViralPotential({ hookScore: 80 })).toBe(80);
  });

  it('returns 0 when given nothing', () => {
    expect(computeViralPotential({})).toBe(0);
  });
});
