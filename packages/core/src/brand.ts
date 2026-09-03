/**
 * The Modern Man brand system.
 *
 * Centralized because the brief requires that changing brand settings changes
 * future content automatically: the design agent, the QA agent, and the
 * dashboard all read from here, so there is exactly one place a color lives.
 */
export const BRAND_COLORS = {
  black: '#080808',
  offWhite: '#F4F1E8',
  gold: '#C9A227',
  darkGray: '#181818',
} as const;

export type BrandColorKey = keyof typeof BRAND_COLORS;

export const DEFAULT_BRAND = {
  name: 'The Modern Man',
  colors: BRAND_COLORS,
  fonts: {
    // A luxury-magazine pairing: high-contrast serif display over a neutral grotesque.
    display: 'Playfair Display',
    body: 'Inter',
    accent: 'Inter',
  },
  tone: [
    'confident',
    'intelligent',
    'modern',
    'ambitious',
    'direct',
    'masculine without being toxic',
    'premium',
    'informative',
    'curious',
  ],
  /** Hard prohibitions. Enforced by the safety agent, not merely suggested in a prompt. */
  avoid: [
    'fake motivation',
    'fabricated quotes',
    'misogyny',
    'rage bait',
    'unsubstantiated wealth claims',
    'invented statistics',
    'cheap clickbait',
    'childish humor',
  ],
  visualDirection: 'luxury magazine × business media × modern menswear editorial',
  defaultSlideCount: 8,
  aspectRatios: { carousel: '4:5', reel: '9:16', story: '9:16' },
} as const;

/** Default content mix, in percent. Must sum to 100. Tuned by the learning engine. */
export const DEFAULT_CONTENT_MIX: Record<string, number> = {
  MONEY: 15,
  BUSINESS: 15,
  AI: 15,
  TECHNOLOGY: 10,
  MINDSET: 10,
  PSYCHOLOGY: 10,
  SPORTS: 8,
  LUXURY: 7,
  LIFESTYLE: 5,
  RELATIONSHIPS: 3,
  NEWS: 2,
};

/** Default topic-scoring weights. Configurable per brand; adjusted by learning. */
export const DEFAULT_SCORING_WEIGHTS: Record<string, number> = {
  CURRENT_INTEREST: 0.12,
  AUDIENCE_FIT: 0.14,
  CURIOSITY: 0.11,
  SHAREABILITY: 0.1,
  SAVEABILITY: 0.09,
  COMMENT_POTENTIAL: 0.06,
  VISUAL_POTENTIAL: 0.08,
  EMOTIONAL_IMPACT: 0.07,
  NOVELTY: 0.07,
  TIMELINESS: 0.06,
  FOLLOW_POTENTIAL: 0.05,
  BRAND_FIT: 0.05,
};
