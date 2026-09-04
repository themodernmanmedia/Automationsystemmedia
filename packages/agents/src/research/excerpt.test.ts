/**
 * Excerpt verification tests.
 *
 * This guard sits between the model and everything downstream: too strict and
 * every claim is dropped, the fact gate blocks the piece, and the system
 * researches, spends, and publishes nothing. Too loose and invented quotes pass
 * as sourced. These cases pin both edges.
 */
import { describe, expect, it } from 'vitest';
import { excerptAppearsIn, normalizeForMatching } from './researcher.js';

const SOURCE = normalizeForMatching(
  `Nvidia reported record quarterly revenue of $60 billion, a 265% increase year over year, ` +
    `driven overwhelmingly by demand for its data centre GPUs. "We are seeing unprecedented ` +
    `demand," chief executive Jensen Huang said on the earnings call — adding that supply ` +
    `remains constrained into next year.`,
);

describe('quotes the model reproduces imperfectly', () => {
  it('accepts an exact quote', () => {
    expect(excerptAppearsIn('record quarterly revenue of $60 billion, a 265% increase', SOURCE)).toBe(true);
  });

  it('accepts a quote whose curly quotes became straight ones', () => {
    // Source has “ ”; the model returns " ". This is the single most common
    // difference between a real quote and its reproduction.
    expect(excerptAppearsIn('"We are seeing unprecedented demand," chief executive Jensen Huang said', SOURCE)).toBe(true);
  });

  it('accepts a quote whose em-dash became a hyphen', () => {
    expect(
      excerptAppearsIn('Jensen Huang said on the earnings call - adding that supply remains constrained', SOURCE),
    ).toBe(true);
  });

  it('accepts a quote with dropped commas and altered spacing', () => {
    expect(
      excerptAppearsIn('driven   overwhelmingly by demand for its data centre GPUs', SOURCE),
    ).toBe(true);
  });

  it('accepts a quote clipped from the middle of a sentence', () => {
    expect(excerptAppearsIn('a 265% increase year over year driven overwhelmingly', SOURCE)).toBe(true);
  });
});

describe('quotes the model did not get from the source', () => {
  it('rejects an invented quote', () => {
    expect(
      excerptAppearsIn('Huang confirmed the company will double manufacturing capacity in Arizona', SOURCE),
    ).toBe(false);
  });

  it('rejects a plausible-sounding quote about the right subject', () => {
    // The hard case: right entities, right register, never actually said.
    expect(
      excerptAppearsIn('Nvidia reported record annual revenue of $90 billion across all divisions', SOURCE),
    ).toBe(false);
  });

  it('rejects a quote assembled from scattered words in the source', () => {
    expect(
      excerptAppearsIn('revenue demand supply constrained increase quarterly centre call', SOURCE),
    ).toBe(false);
  });

  it('rejects an excerpt too short to prove anything', () => {
    expect(excerptAppearsIn('record revenue', SOURCE)).toBe(false);
    expect(excerptAppearsIn('', SOURCE)).toBe(false);
  });
});

describe('normalizeForMatching', () => {
  it('folds the punctuation variants that cause false rejections', () => {
    expect(normalizeForMatching('“Hello,” he said—firmly.')).toBe('hello he said firmly');
    expect(normalizeForMatching("‘quoted’")).toBe('quoted');
  });

  it('keeps numbers, which carry most of the factual weight', () => {
    expect(normalizeForMatching('$60 billion, +265%')).toBe('60 billion 265');
  });
});
