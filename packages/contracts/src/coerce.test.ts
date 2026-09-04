/**
 * First-contact tests.
 *
 * These encode the failure mode this work exists to prevent: a model overruns
 * a cosmetic limit by a few characters and Zod discards the ENTIRE generation —
 * every slide, every beat — after which the caller retries, pays again, and
 * very likely overruns again.
 *
 * The line being drawn: cosmetic limits coerce, semantic ones still reject.
 */
import { describe, expect, it } from 'vitest';
import {
  carouselScriptSchema,
  contentStrategySchema,
  discoveredTopicSchema,
  hookSetSchema,
  reelScriptSchema,
  researchOutputSchema,
  trimToLength,
} from './index.js';

const validSlides = [
  { role: 'HOOK' as const, headline: 'A hook', body: '' },
  { role: 'CONTEXT' as const, headline: 'Context', body: 'Why it matters.' },
  { role: 'POINT' as const, headline: 'A point', body: 'The detail.' },
  { role: 'CTA' as const, headline: 'Follow', body: 'For more.' },
];

describe('trimToLength', () => {
  it('leaves text within the limit untouched', () => {
    expect(trimToLength('short', 90)).toBe('short');
  });

  it('cuts at a word boundary so it does not look broken', () => {
    const result = trimToLength('the quick brown fox jumps over the lazy dog', 20);
    expect(result.length).toBeLessThanOrEqual(20);
    expect(result).toBe('the quick brown fox');
  });

  it('cuts hard rather than discard most of the text to reach a boundary', () => {
    // One early space then a long unbroken run: honoring the boundary would
    // leave almost nothing.
    const result = trimToLength('a ' + 'x'.repeat(200), 50);
    expect(result.length).toBe(50);
  });
});

describe('the failure this prevents', () => {
  it('keeps a whole carousel when one headline overruns by five characters', () => {
    const parsed = carouselScriptSchema.parse({
      title: 'Test',
      slides: [
        { role: 'HOOK', headline: 'x'.repeat(95), body: 'Body copy.' },
        ...validSlides.slice(1),
      ],
      caption: 'A caption',
      hashtags: ['#business'],
    });

    // Previously this threw and took all four slides with it.
    expect(parsed.slides).toHaveLength(4);
    expect(parsed.slides[0]!.headline.length).toBeLessThanOrEqual(90);
  });

  it('keeps a carousel when the body overruns', () => {
    const parsed = carouselScriptSchema.parse({
      title: 'Test',
      slides: [{ ...validSlides[0]!, body: 'word '.repeat(200) }, ...validSlides.slice(1)],
      caption: 'A caption',
      hashtags: [],
    });
    expect(parsed.slides[0]!.body.length).toBeLessThanOrEqual(280);
  });

  it('fills in a body the model omitted entirely', () => {
    const parsed = carouselScriptSchema.parse({
      title: 'Test',
      slides: [{ role: 'HOOK', headline: 'A hook' }, ...validSlides.slice(1)],
      caption: 'c',
      hashtags: [],
    });
    expect(parsed.slides[0]!.body).toBe('');
  });

  it('truncates an over-long hashtag list instead of failing', () => {
    const parsed = carouselScriptSchema.parse({
      title: 'Test',
      slides: validSlides,
      caption: 'c',
      hashtags: Array.from({ length: 50 }, (_, i) => `#tag${i}`),
    });
    expect(parsed.hashtags).toHaveLength(30);
  });

  it('clamps a reel duration the model overshot', () => {
    const parsed = reelScriptSchema.parse({
      title: 'Test',
      beats: [
        { beat: 'HOOK', narration: 'n', visualDirection: 'v', durationSec: 500 },
        { beat: 'BODY', narration: 'n', visualDirection: 'v', durationSec: 0 },
        { beat: 'CTA', narration: 'n', visualDirection: 'v', durationSec: 5 },
      ],
      caption: 'c',
      hashtags: [],
    });
    expect(parsed.beats[0]!.durationSec).toBe(30);
    expect(parsed.beats[1]!.durationSec).toBe(0.5);
  });

  it('clamps out-of-range hook scores', () => {
    const scores = {
      curiosity: 120, clarity: 80, specificity: -10, emotionalImpact: 70,
      scrollStopping: 90, truthfulness: 95, brandFit: 85,
    };
    const parsed = hookSetSchema.parse({
      hooks: [
        { text: 'A specific hook', archetype: 'number-lead', scores },
        { text: 'Another hook', archetype: 'contrarian', scores },
        { text: 'A third hook', archetype: 'question', scores },
      ],
    });
    expect(parsed.hooks[0]!.scores.curiosity).toBe(100);
    expect(parsed.hooks[0]!.scores.specificity).toBe(0);
  });

  it('accepts a concise research summary instead of demanding 50 characters', () => {
    const parsed = researchOutputSchema.parse({
      summary: 'Nvidia beat estimates.',
      keyFindings: ['Revenue rose 265%'],
      angles: [], claims: [], people: [], companies: [],
    });
    expect(parsed.summary).toBe('Nvidia beat estimates.');
    // Omitted entirely by the model, but downstream code iterates it.
    expect(parsed.contradictions).toEqual([]);
  });

  it('accepts a short strategy angle', () => {
    const parsed = contentStrategySchema.parse({
      format: 'CAROUSEL',
      angle: 'Margins',
      storyStructure: 's', audience: 'a', tone: 't',
      visualDirection: 'v', cta: 'c', rationale: 'r',
      targetPlatforms: ['INSTAGRAM'],
    });
    expect(parsed.angle).toBe('Margins');
  });

  it('accepts a topic title shorter than the old eight-character floor', () => {
    const parsed = discoveredTopicSchema.parse({
      title: 'AI capex',
      summary: 'Spending is up.',
      category: 'AI',
      keywords: [], entities: [],
    });
    expect(parsed.title).toBe('AI capex');
  });
});

describe('what still rejects', () => {
  it('rejects an unknown slide role, which would break the designer', () => {
    expect(() =>
      carouselScriptSchema.parse({
        title: 'T',
        slides: [{ role: 'SOMETHING_ELSE', headline: 'h', body: '' }, ...validSlides.slice(1)],
        caption: 'c', hashtags: [],
      }),
    ).toThrow();
  });

  it('rejects a carousel with too few slides to be a carousel', () => {
    expect(() =>
      carouselScriptSchema.parse({
        title: 'T', slides: validSlides.slice(0, 2), caption: 'c', hashtags: [],
      }),
    ).toThrow();
  });

  it('rejects a strategy with nowhere to publish', () => {
    expect(() =>
      contentStrategySchema.parse({
        format: 'CAROUSEL', angle: 'a', storyStructure: 's', audience: 'a',
        tone: 't', visualDirection: 'v', cta: 'c', rationale: 'r',
        targetPlatforms: [],
      }),
    ).toThrow();
  });

  it('rejects an unknown content format', () => {
    expect(() =>
      contentStrategySchema.parse({
        format: 'TIKTOK_LIVE', angle: 'a', storyStructure: 's', audience: 'a',
        tone: 't', visualDirection: 'v', cta: 'c', rationale: 'r',
        targetPlatforms: ['INSTAGRAM'],
      }),
    ).toThrow();
  });

  it('rejects an empty topic title', () => {
    expect(() =>
      discoveredTopicSchema.parse({
        title: '', summary: 's', category: 'AI', keywords: [], entities: [],
      }),
    ).toThrow();
  });
});

describe('excerpts are never trimmed', () => {
  it('preserves a long supporting excerpt so quote verification still works', () => {
    const excerpt = 'word '.repeat(400).trim(); // ~2000 chars
    const parsed = researchOutputSchema.parse({
      summary: 's',
      keyFindings: ['f'],
      angles: [], people: [], companies: [],
      claims: [
        { text: 'A claim', claimType: 'statistic', supportingExcerpt: excerpt, confidence: 0.9 },
      ],
    });
    // Trimming here would break excerpt matching and drop the claim.
    expect(parsed.claims[0]!.supportingExcerpt).toBe(excerpt);
  });
});
