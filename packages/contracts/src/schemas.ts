/**
 * Shared Zod schemas.
 *
 * These are both API boundary validation and the structured-output contracts the
 * agents must satisfy. Using one definition for both means a model that returns
 * a malformed carousel is rejected by the same rules the API would apply.
 */
import { z } from 'zod';

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
  title: z.string().min(8).max(200),
  summary: z.string().min(20).max(1200),
  category: contentCategorySchema,
  keywords: z.array(z.string()).max(15),
  entities: z.array(z.string()).max(20),
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
    Object.fromEntries(SCORING_DIMENSIONS.map((d) => [d, z.number().min(0).max(100)])) as Record<
      (typeof SCORING_DIMENSIONS)[number],
      z.ZodNumber
    >,
  ),
  reasoning: z.string().max(1000),
});
export type TopicScore = z.infer<typeof topicScoreSchema>;

export const extractedClaimSchema = z.object({
  text: z.string().min(5).max(600),
  claimType: z.enum(['statistic', 'date', 'quote', 'event', 'attribution', 'general']),
  /** Must be quoted from the supplied source, never recalled from model memory. */
  supportingExcerpt: z.string().max(1200),
  confidence: z.number().min(0).max(1),
});

export const researchOutputSchema = z.object({
  summary: z.string().min(50),
  keyFindings: z.array(z.string()).min(1).max(12),
  angles: z.array(z.string()).max(8),
  claims: z.array(extractedClaimSchema).max(30),
  people: z.array(z.string()).max(15),
  companies: z.array(z.string()).max(15),
  contradictions: z.array(z.string()).max(8).default([]),
});
export type ResearchOutput = z.infer<typeof researchOutputSchema>;

export const factCheckSchema = z.object({
  results: z.array(
    z.object({
      claimText: z.string(),
      verification: z.enum(['VERIFIED', 'PARTIALLY_VERIFIED', 'UNVERIFIED', 'CONTRADICTED']),
      confidence: z.number().min(0).max(1),
      corroborationCount: z.number().int().min(0),
      notes: z.string().max(600),
      /** A cautious rewrite, when the claim is salvageable but overstated. */
      suggestedRewrite: z.string().max(600).optional(),
    }),
  ),
});
export type FactCheckOutput = z.infer<typeof factCheckSchema>;

export const contentStrategySchema = z.object({
  format: contentFormatSchema,
  angle: z.string().min(10).max(300),
  storyStructure: z.string().max(600),
  audience: z.string().max(300),
  tone: z.string().max(200),
  visualDirection: z.string().max(400),
  cta: z.string().max(200),
  targetPlatforms: z.array(platformSchema).min(1),
  rationale: z.string().max(800),
});
export type ContentStrategy = z.infer<typeof contentStrategySchema>;

export const hookSchema = z.object({
  text: z.string().min(5).max(200),
  archetype: z.string().max(60),
  scores: z.object({
    curiosity: z.number().min(0).max(100),
    clarity: z.number().min(0).max(100),
    specificity: z.number().min(0).max(100),
    emotionalImpact: z.number().min(0).max(100),
    scrollStopping: z.number().min(0).max(100),
    truthfulness: z.number().min(0).max(100),
    brandFit: z.number().min(0).max(100),
  }),
});

export const hookSetSchema = z.object({ hooks: z.array(hookSchema).min(5) });
export type HookSet = z.infer<typeof hookSetSchema>;

export const SLIDE_ROLES = ['HOOK', 'CONTEXT', 'POINT', 'TAKEAWAY', 'CTA'] as const;

export const carouselScriptSchema = z.object({
  title: z.string().max(200),
  slides: z
    .array(
      z.object({
        role: z.enum(SLIDE_ROLES),
        headline: z.string().max(90),
        // Kept short deliberately: the brief forbids giant blocks of text.
        body: z.string().max(280).default(''),
        visualNote: z.string().max(200).optional(),
      }),
    )
    .min(4)
    .max(10),
  caption: z.string().max(2200),
  hashtags: z.array(z.string()).max(30),
});
export type CarouselScript = z.infer<typeof carouselScriptSchema>;

export const REEL_BEATS = ['HOOK', 'SETUP', 'BODY', 'PATTERN_INTERRUPT', 'PAYOFF', 'CTA'] as const;

export const reelScriptSchema = z.object({
  title: z.string().max(200),
  beats: z
    .array(
      z.object({
        beat: z.enum(REEL_BEATS),
        narration: z.string().max(400),
        onScreenText: z.string().max(120).optional(),
        visualDirection: z.string().max(300),
        durationSec: z.number().min(0.5).max(30),
      }),
    )
    .min(3),
  caption: z.string().max(2200),
  hashtags: z.array(z.string()).max(30),
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
      message: z.string().max(400),
      excerpt: z.string().max(300).optional(),
    }),
  ),
});
export type SafetyReview = z.infer<typeof safetyReviewSchema>;

export const brandQaSchema = z.object({
  verdict: z.enum(['PASS', 'WARN', 'FAIL']),
  score: z.number().min(0).max(100),
  findings: z.array(
    z.object({
      field: z.string().max(60),
      severity: z.enum(['LOW', 'MEDIUM', 'HIGH']),
      message: z.string().max(400),
      suggestion: z.string().max(400).optional(),
    }),
  ),
});
export type BrandQa = z.infer<typeof brandQaSchema>;
