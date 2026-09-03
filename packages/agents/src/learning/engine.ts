/**
 * LEARNING ENGINE.
 *
 * Turns measured performance into adjusted scoring weights and format
 * allocation. Three constraints keep it from destroying the account:
 *
 *  1. A sample-size floor. Three lucky posts must not rewrite strategy.
 *  2. Bounded steps. No weight moves more than a fixed amount per cycle, so a
 *     single anomalous week cannot collapse the mix into one category.
 *  3. Full auditability. Every adjustment records what moved and why.
 *
 * The brief also warns against optimizing for volume. So the objective function
 * weights saves, shares, and watch time — signals of value — above raw views.
 */
export interface PostPerformance {
  contentPieceId: string;
  category: string;
  format: string;
  hookArchetype?: string;
  slideCount?: number;
  reelLengthSec?: number;
  postedAtHour: number;
  postedAtWeekday: number;
  views: number | null;
  reach: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  avgWatchTimeSec: number | null;
  followsGained: number | null;
}

/**
 * Composite value of a post.
 *
 * Weighted toward saves, shares and follows because those indicate the content
 * was worth keeping or passing on. Views alone measure distribution, not value,
 * and optimizing for views produces exactly the volume trap the brief rejects.
 */
export function performanceScore(p: PostPerformance): number | null {
  const reach = p.reach ?? p.views;
  if (!reach || reach <= 0) return null; // no denominator, no comparable score

  const weighted =
    (p.saves ?? 0) * 3 + (p.shares ?? 0) * 3 + (p.followsGained ?? 0) * 5 + (p.comments ?? 0) * 2 + (p.likes ?? 0) * 1;

  // Per-1000-reached, so a small account's good post is comparable to a big one's.
  return Number(((weighted / reach) * 1000).toFixed(3));
}

export interface DimensionInsight {
  dimension: string;
  key: string;
  sampleSize: number;
  avgScore: number;
  liftVsBaseline: number;
  confidence: number;
}

/** Below this, a group is reported but never allowed to move a weight. */
export const MIN_SAMPLE_SIZE = 5;

export function computeInsights(posts: PostPerformance[]): {
  baseline: number;
  insights: DimensionInsight[];
} {
  const scored = posts
    .map((p) => ({ post: p, score: performanceScore(p) }))
    .filter((s): s is { post: PostPerformance; score: number } => s.score !== null);

  if (scored.length === 0) return { baseline: 0, insights: [] };

  const baseline = scored.reduce((sum, s) => sum + s.score, 0) / scored.length;
  if (baseline === 0) return { baseline: 0, insights: [] };

  const dimensions: Array<[string, (p: PostPerformance) => string | undefined]> = [
    ['category', (p) => p.category],
    ['format', (p) => p.format],
    ['hook_archetype', (p) => p.hookArchetype],
    ['slide_count', (p) => (p.slideCount ? String(p.slideCount) : undefined)],
    ['reel_length', (p) => (p.reelLengthSec ? bucketDuration(p.reelLengthSec) : undefined)],
    ['posting_hour', (p) => bucketHour(p.postedAtHour)],
    ['posting_weekday', (p) => String(p.postedAtWeekday)],
  ];

  const insights: DimensionInsight[] = [];
  for (const [dimension, pick] of dimensions) {
    const groups = new Map<string, number[]>();
    for (const { post, score } of scored) {
      const key = pick(post);
      if (!key) continue;
      const list = groups.get(key) ?? [];
      list.push(score);
      groups.set(key, list);
    }

    for (const [key, scores] of groups) {
      const avgScore = scores.reduce((a, b) => a + b, 0) / scores.length;
      insights.push({
        dimension,
        key,
        sampleSize: scores.length,
        avgScore: Number(avgScore.toFixed(3)),
        liftVsBaseline: Number((avgScore / baseline).toFixed(3)),
        confidence: confidenceFor(scores.length),
      });
    }
  }

  insights.sort((a, b) => b.liftVsBaseline - a.liftVsBaseline);
  return { baseline: Number(baseline.toFixed(3)), insights };
}

/**
 * Confidence grows with sample size and saturates. Not a statistical
 * significance test — an honest heuristic for "how much should this move
 * anything", used as a damping factor rather than as a claim about p-values.
 */
function confidenceFor(sampleSize: number): number {
  if (sampleSize < MIN_SAMPLE_SIZE) return 0;
  return Number(Math.min(0.95, 1 - Math.exp(-sampleSize / 15)).toFixed(3));
}

function bucketDuration(sec: number): string {
  if (sec < 15) return '0-15s';
  if (sec < 30) return '15-30s';
  if (sec < 45) return '30-45s';
  if (sec < 60) return '45-60s';
  return '60s+';
}

function bucketHour(hour: number): string {
  if (hour < 6) return 'night (00-06)';
  if (hour < 12) return 'morning (06-12)';
  if (hour < 17) return 'afternoon (12-17)';
  if (hour < 21) return 'evening (17-21)';
  return 'late (21-24)';
}

export interface WeightAdjustment {
  dimension: string;
  from: number;
  to: number;
  reason: string;
}

/**
 * Adjusts topic-scoring weights from measured performance.
 *
 * `maxStep` is the whole safety mechanism: even a wildly anomalous week can
 * only nudge a weight, so the system drifts toward what works instead of
 * lurching toward whatever happened last.
 */
export function adjustScoringWeights(
  currentWeights: Record<string, number>,
  insights: DimensionInsight[],
  maxStep = 0.02,
): { weights: Record<string, number>; adjustments: WeightAdjustment[] } {
  const adjustments: WeightAdjustment[] = [];
  const weights = { ...currentWeights };

  // Categories that consistently outperform imply AUDIENCE_FIT and BRAND_FIT
  // are carrying real signal, so those dimensions earn more weight.
  const categoryInsights = insights.filter(
    (i) => i.dimension === 'category' && i.sampleSize >= MIN_SAMPLE_SIZE,
  );
  if (categoryInsights.length >= 3) {
    const spread = Math.max(...categoryInsights.map((i) => i.liftVsBaseline)) -
      Math.min(...categoryInsights.map((i) => i.liftVsBaseline));
    // A wide spread means category choice matters a lot for this audience.
    if (spread > 0.5) {
      for (const dimension of ['AUDIENCE_FIT', 'BRAND_FIT']) {
        const from = weights[dimension];
        if (from === undefined) continue;
        const to = Number(Math.min(0.3, from + maxStep).toFixed(4));
        if (to !== from) {
          weights[dimension] = to;
          adjustments.push({
            dimension,
            from,
            to,
            reason: `Category performance varies widely (${spread.toFixed(2)}x spread across ${categoryInsights.length} categories), so audience and brand fit are strong predictors.`,
          });
        }
      }
    }
  }

  // If saveable, shareable formats dominate, weight those dimensions up.
  const formatInsights = insights.filter(
    (i) => i.dimension === 'format' && i.sampleSize >= MIN_SAMPLE_SIZE,
  );
  const bestFormat = formatInsights[0];
  if (bestFormat && bestFormat.liftVsBaseline > 1.25) {
    for (const dimension of ['SAVEABILITY', 'SHAREABILITY']) {
      const from = weights[dimension];
      if (from === undefined) continue;
      const to = Number(Math.min(0.3, from + maxStep * bestFormat.confidence).toFixed(4));
      if (to !== from) {
        weights[dimension] = to;
        adjustments.push({
          dimension,
          from,
          to,
          reason: `${bestFormat.key} outperforms baseline by ${bestFormat.liftVsBaseline.toFixed(2)}x over ${bestFormat.sampleSize} posts.`,
        });
      }
    }
  }

  // Renormalize so the weights remain a valid distribution.
  const sum = Object.values(weights).reduce((a, b) => a + b, 0);
  if (sum > 0) {
    for (const key of Object.keys(weights)) {
      weights[key] = Number(((weights[key] ?? 0) / sum).toFixed(4));
    }
  }

  return { weights, adjustments };
}

/**
 * Best posting windows from measured performance.
 *
 * Returns nothing until there is enough history — the brief warns against fixed
 * times forever, but guessing from three posts is not better than a default.
 */
export function optimalPostingHours(
  posts: PostPerformance[],
  slotsWanted = 4,
): Array<{ hour: number; avgScore: number; sampleSize: number }> {
  const byHour = new Map<number, number[]>();
  for (const post of posts) {
    const score = performanceScore(post);
    if (score === null) continue;
    const list = byHour.get(post.postedAtHour) ?? [];
    list.push(score);
    byHour.set(post.postedAtHour, list);
  }

  return [...byHour.entries()]
    .map(([hour, scores]) => ({
      hour,
      avgScore: Number((scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(3)),
      sampleSize: scores.length,
    }))
    .filter((h) => h.sampleSize >= 3)
    .sort((a, b) => b.avgScore - a.avgScore)
    .slice(0, slotsWanted);
}
