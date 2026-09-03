import { describe, expect, it } from 'vitest';
import { contentHash, findDuplicates, isDuplicate, similarity, SIMILARITY_THRESHOLDS } from './dedupe.js';

describe('similarity', () => {
  it('scores identical text as 1', () => {
    expect(similarity('Nvidia beats earnings expectations', 'Nvidia beats earnings expectations')).toBe(1);
  });

  it('ignores punctuation and casing', () => {
    expect(similarity('Nvidia Beats Earnings!', 'nvidia beats earnings')).toBeGreaterThan(0.9);
  });

  it('scores unrelated text near zero', () => {
    expect(similarity('Nvidia beats earnings', 'How to cook a steak')).toBeLessThan(0.3);
  });

  it('catches the same story reported by different outlets', () => {
    const a = 'Nvidia reports record quarterly revenue of $60 billion, beating analyst expectations';
    const b = 'Nvidia posts record quarterly revenue of $60 billion, exceeding analyst estimates';
    expect(similarity(a, b)).toBeGreaterThan(SIMILARITY_THRESHOLDS.topic);
  });

  it('does not conflate two different takes on the same subject', () => {
    const a = 'Nvidia reports record quarterly revenue driven by data centre demand';
    const b = 'Why Nvidia is losing the inference market to custom silicon from cloud providers';
    expect(similarity(a, b)).toBeLessThan(SIMILARITY_THRESHOLDS.topic);
  });

  it('handles empty input without dividing by zero', () => {
    expect(similarity('', 'anything')).toBe(0);
    expect(similarity('', '')).toBe(0);
  });

  it('is symmetric', () => {
    const a = 'The Fed holds rates steady';
    const b = 'Federal Reserve keeps rates unchanged';
    expect(similarity(a, b)).toBeCloseTo(similarity(b, a), 5);
  });
});

describe('findDuplicates', () => {
  const candidates = [
    { id: '1', text: 'Nvidia reports record quarterly revenue of $60 billion' },
    { id: '2', text: 'Apple announces a new foldable iPhone for 2027' },
    { id: '3', text: 'Nvidia posts record quarterly revenue of $60 billion' },
  ];

  it('finds matches ordered by similarity', () => {
    const matches = findDuplicates('Nvidia reports record quarterly revenue of $60 billion', candidates);
    expect(matches[0]!.id).toBe('1');
    expect(matches.map((m) => m.id)).toContain('3');
    expect(matches.map((m) => m.id)).not.toContain('2');
  });

  it('reports no duplicate for a genuinely new topic', () => {
    expect(isDuplicate('Tesla opens a new gigafactory in Mexico', candidates)).toBe(false);
  });
});

describe('contentHash', () => {
  it('is stable across formatting differences', () => {
    expect(contentHash('Hello,   World!')).toBe(contentHash('hello world'));
  });

  it('differs for different content', () => {
    expect(contentHash('Hello World')).not.toBe(contentHash('Goodbye World'));
  });
});
