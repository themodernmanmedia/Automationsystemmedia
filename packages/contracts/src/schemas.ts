/**
 * Shared Zod schemas.
 *
 * These are both API boundary validation and the structured-output contracts the
 * agents must satisfy. Using one definition for both means a model that returns
 * a malformed carousel is rejected by the same rules the API would apply.
 */
import { z } from 'zod';
import { clampedArray, clampedNumber, clampedString, clampedStringOptional, clampedStringWithDefault } from './coerce.js';

export const platformSchema = z.enum([
  'INSTAGRAM', 'TIKTOK', 'FACEBOOK', 'YOUTUBE', 'X', 'LINKEDIN', 'PINTEREST', 'THREADS',
]);

export const contentCategorySchema = z.enum([
  'MONEY', 'BUSINESS', 'AI', 'TECHNOLOGY', 'MINDSET', 'PSYCHOLOGY',
  'SPORTS', 'LUXURY', 'LIFESTYLE', 'RELATIONSHIPS', 'NEWS',
]);

export const contentFormatSchema = z.enum(['CAROUSEL', 'REEL', 'SINGLE_IMAGE', 'STORY', 'SERIES']);

/* ----------------------------- agent outputs ----------------------------- */

export const discoveredTopicSchema = z.object({
  // Minimums dropped: they rejected usable topics for being concise, and a
  // genuinely empty title fails the non-empty check below anyway.
  title: clampedString(200).pipe(z.string().min(1)),
  summary: clampedString(1200),
  category: contentCategorySchema,
  keywords: clampedArray(z.string(), { max: 15 }),
  entities: clampedArray(z.string(), { max: 20 }),
  isBreakingNews: z.boolean().default(false),
});
export type DiscoveredTopic = z.infer<typeof discoveredTopicSchema>;

export const SCORING_DIMENSIONS = [
  'CURRENT_INTEREST', 'AUDIENCE_FIT', 'CURIOSITY', 'SHAREABILITY', 'SAVEABILITY',
  'COMMENT_POTENTIAL', 'VISUAL_POTENTIAL', 'EMOTIONAL_IMPACT', 'NOVELTY',
  'TIMELINESS', 'FOLLOW_POTENTIAL', 'BRAND_FIT',
] as const;

export const topicScoreSchema = z.object({
  scores: z.object(
    Object.fromEntries(SCORING_DIMENSIONS.map((d) => [d, clampedNumber(0, 100)])) as Record<
      (typeof SCORING_DIMENSIONS)[number],
      ReturnType<typeof clampedNumber>
    >,
  ),
  reasoning: clampedString(1000),
});
export type TopicScore = z.infer<typeof topicScoreSchema>;

export const extractedClaimSchema = z.object({
  text: clampedString(600).pipe(z.string().min(5)),
  // claimType stays a strict enum: an unrecognized value means the model
  // misread the task, and guessing a category would corrupt the record.
  claimType: z.enum(['statistic', 'date', 'quote', 'event', 'attribution', 'general']),
  /** Must be quoted from the supplied source, never recalled from model memory.
   *  Never clamped — truncating a quote would break excerpt verification. */
  supportingExcerpt: z.string().max(4000),
  confidence: clampedNumber(0, 1),
});

export const researchOutputSchema = z.object({
  // min(50) rejected concise-but-usable summaries; a genuinely empty one is
  // still caught, and thin research is handled by the fact gate downstream.
  summary: z.string().min(1),
  keyFindings: clampedArray(z.string(), { min: 1, max: 12 }),
  angles: clampedArray(z.string(), { max: 8 }),
  claims: clampedArray(extractedClaimSchema, { max: 30 }),
  people: clampedArray(z.string(), { max: 15 }),
  companies: clampedArray(z.string(), { max: 15 }),
  contradictions: clampedArray(z.string(), { max: 8 }).default([]),
});
export type ResearchOutput = z.infer<typeof researchOutputSchema>;

export const factCheckSchema = z.object({
  results: z.array(
    z.object({
      claimText: z.string(),
      verification: z.enum(['VERIFIED', 'PARTIALLY_VERIFIED', 'UNVERIFIED', 'CONTRADICTED']),
      confidence: clampedNumber(0, 1),
      corroborationCount: z.number().int().min(0).catch(0),
      notes: clampedString(600),
      /** A cautious rewrite, when the claim is salvageable but overstated. */
      suggestedRewrite: clampedStringOptional(600),
    }),
  ),
});
export type FactCheckOutput = z.infer<typeof factCheckSchema>;

export const contentStrategySchema = z.object({
  format: contentFormatSchema,
  angle: clampedString(300).pipe(z.string().min(1)),
  storyStructure: clampedString(600),
  audience: clampedString(300),
  tone: clampedString(200),
  visualDirection: clampedString(400),
  cta: clampedString(200),
  // Strict: with no target there is nowhere to publish, and inventing one
  // would post to an account the strategist never chose.
  targetPlatforms: z.array(platformSchema).min(1),
  rationale: clampedString(800),
});
export type ContentStrategy = z.infer<typeof contentStrategySchema>;

export const hookSchema = z.object({
  text: clampedString(200).pipe(z.string().min(5)),
  archetype: clampedString(60),
  scores: z.object({
    curiosity: clampedNumber(0, 100),
    clarity: clampedNumber(0, 100),
    specificity: clampedNumber(0, 100),
    emotionalImpact: clampedNumber(0, 100),
    scrollStopping: clampedNumber(0, 100),
    // Clamped like the rest, but the TRUTHFULNESS FLOOR that rejects
    // misleading hooks is applied in the hook engine, not here.
    truthfulness: clampedNumber(0, 100),
    brandFit: clampedNumber(0, 100),
  }),
});

export const hookSetSchema = z.object({ hooks: z.array(hookSchema).min(3) });
export type HookSet = z.infer<typeof hookSetSchema>;

export const SLIDE_ROLES = ['HOOK', 'CONTEXT', 'POINT', 'TAKEAWAY', 'CTA'] as const;

export const carouselScriptSchema = z.object({
  title: clampedString(200),
  slides: clampedArray(
    z.object({
      // Strict: an unknown role would break the designer's layout rules.
      role: z.enum(SLIDE_ROLES),
      // Trimmed, not rejected. Models are unreliable at counting characters,
      // and a 95-character headline must not discard the whole carousel.
      headline: clampedString(90),
      // Kept short deliberately: the brief forbids giant blocks of text.
      body: clampedStringWithDefault(280),
      visualNote: clampedStringOptional(200),
    }),
    // min stays strict: fewer than four slides is not a carousel, and
    // Instagram itself requires at least two.
    { min: 4, max: 10 },
  ),
  caption: clampedString(2200),
  hashtags: clampedArray(z.string(), { max: 30 }),
});
export type CarouselScript = z.infer<typeof carouselScriptSchema>;

export const REEL_BEATS = ['HOOK', 'SETUP', 'BODY', 'PATTERN_INTERRUPT', 'PAYOFF', 'CTA'] as const;

export const reelScriptSchema = z.object({
  title: clampedString(200),
  beats: clampedArray(
    z.object({
      beat: z.enum(REEL_BEATS),
      narration: clampedString(400),
      onScreenText: clampedStringOptional(120),
      visualDirection: clampedString(300),
      // Clamped: the render job replaces these with measured speech duration
      // anyway, so an out-of-range estimate is not worth failing over.
      durationSec: clampedNumber(0.5, 30),
    }),
    { min: 3, max: 20 },
  ),
  caption: clampedString(2200),
  hashtags: clampedArray(z.string(), { max: 30 }),
});
export type ReelScript = z.infer<typeof reelScriptSchema>;

export const safetyReviewSchema = z.object({
  verdict: z.enum(['PASS', 'WARN', 'FAIL']),
  findings: z.array(
    z.object({
      category: z.enum([
        'hate', 'harassment', 'sexual', 'misinformation', 'fraud', 'scam',
        'illegal', 'unverified_allegation', 'defamation', 'copyright', 'brand_violation',
      ]),
      severity: z.enum(['LOW', 'MEDIUM', 'HIGH']),
      message: clampedString(400),
      excerpt: clampedStringOptional(300),
    }),
  ),
});
export type SafetyReview = z.infer<typeof safetyReviewSchema>;

export const brandQaSchema = z.object({
  verdict: z.enum(['PASS', 'WARN', 'FAIL']),
  score: clampedNumber(0, 100),
  findings: z.array(
    z.object({
      field: clampedString(60),
      severity: z.enum(['LOW', 'MEDIUM', 'HIGH']),
      message: clampedString(400),
      suggestion: clampedStringOptional(400),
    }),
  ),
});
export type BrandQa = z.infer<typeof brandQaSchema>;
