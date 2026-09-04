/**
 * Experiment engine tests.
 *
 * The risk this guards is calling a winner from noise. A social account
 * produces tens of posts, not thousands, so a naive "higher mean wins" would
 * promote a variant on luck and then bake that luck into strategy.
 */
import { describe, expect, it } from 'vitest';
import { ValidationError } from '@mmos/core';
import {
  analyzeExperiment,
  assignVariant,
  compare,
  criticalT95,
  summarize,
  validateExperiment,
  type ExperimentVariant,
} from './experiments.js';

const variants: ExperimentVariant[] = [
  { key: 'number_lead', description: 'Open with the statistic' },
  { key: 'contrarian', description: 'Open by contradicting a belief' },
];

describe('the single-variable rule', () => {
  it('accepts a well-formed experiment', () => {
    expect(() =>
      validateExperiment({
        name: 'Hook style', hypothesis: 'Number-led hooks save better', variable: 'hook', variants,
      }),
    ).not.toThrow();
  });

  it('rejects a variable that is not testable', () => {
    expect(() =>
      validateExperiment({
        name: 'x', hypothesis: 'y', variable: 'everything' as never, variants,
      }),
    ).toThrow(ValidationError);
  });

  it('rejects a single variant, which compares nothing', () => {
    expect(() =>
      validateExperiment({ name: 'x', hypothesis: 'y', variable: 'hook', variants: [variants[0]!] }),
    ).toThrow(/at least two variants/);
  });

  it('rejects too many arms, which split a small sample too thinly', () => {
    const many = Array.from({ length: 5 }, (_, i) => ({ key: `v${i}`, description: 'd' }));
    expect(() =>
      validateExperiment({ name: 'x', hypothesis: 'y', variable: 'hook', variants: many }),
    ).toThrow(/too thinly/);
  });

  it('rejects duplicate variant keys', () => {
    expect(() =>
      validateExperiment({
        name: 'x', hypothesis: 'y', variable: 'hook',
        variants: [{ key: 'a', description: '1' }, { key: 'a', description: '2' }],
      }),
    ).toThrow(/unique/);
  });

  it('rejects a sample floor too low to mean anything', () => {
    expect(() =>
      validateExperiment({ name: 'x', hypothesis: 'y', variable: 'hook', variants, minSampleSize: 3 }),
    ).toThrow(/at least 5/);
  });
});

describe('assignment', () => {
  it('is deterministic, so a retry cannot move a piece between arms', () => {
    const first = assignVariant('exp-1', 'piece-42', variants);
    for (let i = 0; i < 20; i++) {
      expect(assignVariant('exp-1', 'piece-42', variants)).toBe(first);
    }
  });

  it('separates different pieces', () => {
    const assignments = Array.from({ length: 200 }, (_, i) =>
      assignVariant('exp-1', `piece-${i}`, variants),
    );
    const counts = new Map<string, number>();
    for (const key of assignments) counts.set(key, (counts.get(key) ?? 0) + 1);

    expect(counts.size).toBe(2);
    // Roughly balanced; exact parity is not required, gross skew would be a bug.
    for (const count of counts.values()) {
      expect(count).toBeGreaterThan(60);
    }
  });

  it('assigns the same piece differently across experiments', () => {
    const a = Array.from({ length: 50 }, (_, i) => assignVariant('exp-A', `p${i}`, variants));
    const b = Array.from({ length: 50 }, (_, i) => assignVariant('exp-B', `p${i}`, variants));
    // Independent experiments must not correlate their arms.
    expect(a.join('')).not.toBe(b.join(''));
  });
});

describe('summarize', () => {
  it('computes mean and sample standard deviation', () => {
    const stats = summarize('a', [2, 4, 4, 4, 5, 5, 7, 9]);
    expect(stats.mean).toBe(5);
    // Sample sd (n-1), not population sd, since these are samples.
    expect(stats.stdDev).toBeCloseTo(2.138, 2);
    expect(stats.standardError).toBeCloseTo(0.756, 2);
  });

  it('handles an empty arm without dividing by zero', () => {
    expect(summarize('a', [])).toMatchObject({ sampleSize: 0, mean: 0, stdDev: 0 });
  });
});

describe('criticalT95', () => {
  it('matches published two-sided 95% values', () => {
    expect(criticalT95(1)).toBe(12.706);
    expect(criticalT95(10)).toBe(2.228);
    expect(criticalT95(30)).toBe(2.042);
  });

  it('is stricter for small samples than large', () => {
    expect(criticalT95(3)).toBeGreaterThan(criticalT95(30));
  });

  it('approaches the normal value for large samples', () => {
    expect(criticalT95(500)).toBe(1.96);
  });
});

describe("Welch's t-test", () => {
  it('detects a genuine, large separation', () => {
    const a = summarize('a', [50, 52, 48, 51, 49, 53, 47, 50, 52, 51]);
    const b = summarize('b', [20, 22, 18, 21, 19, 23, 17, 20, 22, 21]);
    const result = compare(a, b)!;

    expect(result.leader).toBe('a');
    expect(result.significant).toBe(true);
    expect(result.lift).toBeCloseTo(2.5, 1);
  });

  it('refuses to separate arms that merely differ by chance', () => {
    // Overlapping spreads, small difference in means: the classic false positive.
    const a = summarize('a', [10, 30, 15, 25, 20, 35, 5, 22, 18, 28]);
    const b = summarize('b', [12, 28, 14, 26, 19, 31, 8, 20, 17, 25]);
    const result = compare(a, b)!;

    expect(result.significant).toBe(false);
  });

  it('is not fooled by one arm having wider spread', () => {
    // Same means, very different variance. Student's t would understate this;
    // Welch's is the reason we do not claim a winner here.
    const a = summarize('a', [30, 30, 30, 30, 30, 30, 30, 30]);
    const b = summarize('b', [5, 55, 10, 50, 15, 45, 20, 40]);
    expect(compare(a, b)!.significant).toBe(false);
  });

  it('returns nothing when an arm is too small to have variance', () => {
    expect(compare(summarize('a', [10]), summarize('b', [20, 30]))).toBeNull();
  });

  it('handles identical observations without dividing by zero', () => {
    const result = compare(summarize('a', [10, 10, 10]), summarize('b', [10, 10, 10]))!;
    expect(result.significant).toBe(false);
    expect(Number.isFinite(result.tStatistic)).toBe(true);
  });
});

describe('analyzeExperiment', () => {
  it('keeps collecting until every arm meets the floor', () => {
    const analysis = analyzeExperiment(
      { number_lead: [40, 45, 50], contrarian: [20, 25] },
      variants,
      10,
    );
    expect(analysis.verdict).toBe('COLLECTING');
    expect(analysis.shortfall['number_lead']).toBe(7);
    expect(analysis.shortfall['contrarian']).toBe(8);
    expect(analysis.winner).toBeUndefined();
  });

  it('declares a winner when the arms genuinely separate', () => {
    const analysis = analyzeExperiment(
      {
        number_lead: [50, 52, 48, 51, 49, 53, 47, 50, 52, 51],
        contrarian: [20, 22, 18, 21, 19, 23, 17, 20, 22, 21],
      },
      variants,
      10,
    );
    expect(analysis.verdict).toBe('WINNER');
    expect(analysis.winner).toBe('number_lead');
    expect(analysis.conclusion).toMatch(/95% confidence/);
  });

  it('records INCONCLUSIVE as a real result rather than promoting the leader', () => {
    const analysis = analyzeExperiment(
      {
        number_lead: [10, 30, 15, 25, 20, 35, 5, 22, 18, 28],
        contrarian: [12, 28, 14, 26, 19, 31, 8, 20, 17, 25],
      },
      variants,
      10,
    );
    expect(analysis.verdict).toBe('INCONCLUSIVE');
    // The leading arm must NOT be adopted on a difference this small.
    expect(analysis.winner).toBeUndefined();
    expect(analysis.conclusion).toMatch(/within the noise/);
  });

  it('compares the leader against the best of the rest with three arms', () => {
    const three: ExperimentVariant[] = [
      ...variants,
      { key: 'question', description: 'Open with a question' },
    ];
    const analysis = analyzeExperiment(
      {
        number_lead: [50, 52, 48, 51, 49, 53, 47, 50, 52, 51],
        contrarian: [20, 22, 18, 21, 19, 23, 17, 20, 22, 21],
        question: [30, 32, 28, 31, 29, 33, 27, 30, 32, 31],
      },
      three,
      10,
    );
    expect(analysis.winner).toBe('number_lead');
    // Compared against `question` (the runner-up), not the weakest arm — which
    // is the harder and more honest test.
    expect(analysis.comparison!.challenger).toBe('question');
  });
});
