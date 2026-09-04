/**
 * Learning cycle.
 *
 * Reads what actually happened, and writes the result back into the decisions
 * that drive the next cycle. Without this the system produces content forever
 * without ever getting better at it, which is the difference between automation
 * and a media operation.
 *
 * Three constraints keep it from destroying the account:
 *   - a sample-size floor, so three lucky posts cannot rewrite strategy
 *   - bounded weight steps, so one anomalous week cannot collapse the mix
 *   - every adjustment recorded, so a bad cycle is explainable and reversible
 */
import { type Logger } from '@mmos/core';
import { prisma } from '@mmos/db';
import {
  MIN_SAMPLE_SIZE,
  adjustMixByPerformance,
  adjustScoringWeights,
  computeInsights,
  optimalPostingHours,
  type PostPerformance,
} from '@mmos/agents';
import type { AutomationService } from '@mmos/engine';

export interface LearningDeps {
  organizationId: string;
  automation: AutomationService;
  logger: Logger;
}

export interface LearningCycleResult {
  postsAnalyzed: number;
  insightsWritten: number;
  weightsAdjusted: number;
  mixAdjusted: boolean;
  learnedPostingHours: number[];
  /** Absent when there was too little data to act on. */
  skippedReason?: string;
}

/**
 * Runs one learning cycle over the trailing window.
 *
 * 30 days by default: long enough for a meaningful sample at a few posts a day,
 * short enough that the strategy still reflects the current audience rather
 * than last quarter's.
 */
export async function runLearningCycle(
  deps: LearningDeps,
  windowDays = 30,
): Promise<LearningCycleResult> {
  await deps.automation.assertMayRun(deps.organizationId, 'learningEngine');

  const windowEnd = new Date();
  const windowStart = new Date(windowEnd.getTime() - windowDays * 86_400_000);
  const log = deps.logger.child({ organizationId: deps.organizationId, windowDays });

  // Only the newest reading per post, so a post measured five times does not
  // count five times and drown out everything else.
  const records = await prisma.analyticsRecord.findMany({
    where: {
      socialAccount: { organizationId: deps.organizationId },
      collectedAt: { gte: windowStart },
      publishingJob: { isNot: null },
    },
    orderBy: { collectedAt: 'desc' },
    include: {
      publishingJob: {
        include: {
          contentPiece: {
            select: { id: true, category: true, format: true, hookArchetype: true },
            
          },
          
        },
      },
    },
  });

  const latestByPost = new Map<string, (typeof records)[number]>();
  for (const record of records) {
    if (!latestByPost.has(record.platformPostId)) latestByPost.set(record.platformPostId, record);
  }

  const contentPieceIds = [...new Set(
    [...latestByPost.values()].map((r) => r.publishingJob?.contentPieceId).filter((id): id is string => Boolean(id)),
  )];

  const [carousels, reels] = await Promise.all([
    prisma.carouselPost.findMany({
      where: { contentPieceId: { in: contentPieceIds } },
      select: { contentPieceId: true, slideCount: true },
    }),
    prisma.reel.findMany({
      where: { contentPieceId: { in: contentPieceIds } },
      select: { contentPieceId: true, durationSec: true },
    }),
  ]);
  const slideCounts = new Map(carousels.map((c) => [c.contentPieceId, c.slideCount]));
  const reelLengths = new Map(reels.map((r) => [r.contentPieceId, r.durationSec]));

  const posts: PostPerformance[] = [];
  for (const record of latestByPost.values()) {
    const piece = record.publishingJob?.contentPiece;
    const publishedAt = record.publishingJob?.publishedAt;
    if (!piece || !publishedAt) continue;

    const slideCount = slideCounts.get(piece.id);
    const reelLength = reelLengths.get(piece.id);

    posts.push({
      contentPieceId: piece.id,
      category: piece.category,
      format: piece.format,
      ...(piece.hookArchetype ? { hookArchetype: piece.hookArchetype } : {}),
      ...(slideCount !== undefined ? { slideCount } : {}),
      ...(reelLength ? { reelLengthSec: reelLength } : {}),
      postedAtHour: publishedAt.getUTCHours(),
      postedAtWeekday: publishedAt.getUTCDay(),
      views: record.views,
      reach: record.reach,
      likes: record.likes,
      comments: record.comments,
      shares: record.shares,
      saves: record.saves,
      avgWatchTimeSec: record.avgWatchTimeSec,
      followsGained: record.followsGained,
    });
  }

  if (posts.length < MIN_SAMPLE_SIZE) {
    const reason = `Only ${posts.length} measured post(s) in the window; the minimum sample is ${MIN_SAMPLE_SIZE}. Nothing was adjusted.`;
    log.info({ posts: posts.length }, 'learning cycle skipped: not enough data');
    return {
      postsAnalyzed: posts.length,
      insightsWritten: 0,
      weightsAdjusted: 0,
      mixAdjusted: false,
      learnedPostingHours: [],
      skippedReason: reason,
    };
  }

  /* ---- insights ---- */

  const { baseline, insights } = computeInsights(posts);

  let insightsWritten = 0;
  for (const insight of insights) {
    await prisma.learningInsight.upsert({
      where: {
        organizationId_dimension_key_windowEnd: {
          organizationId: deps.organizationId,
          dimension: insight.dimension,
          key: insight.key,
          windowEnd,
        },
      },
      create: {
        organizationId: deps.organizationId,
        dimension: insight.dimension,
        key: insight.key,
        sampleSize: insight.sampleSize,
        avgEngagement: insight.avgScore,
        liftVsBaseline: insight.liftVsBaseline,
        confidence: insight.confidence,
        windowStart,
        windowEnd,
      },
      update: {
        sampleSize: insight.sampleSize,
        avgEngagement: insight.avgScore,
        liftVsBaseline: insight.liftVsBaseline,
        confidence: insight.confidence,
      },
    });
    insightsWritten++;
  }

  /* ---- feed the insights back into the next cycle's decisions ---- */

  const brand = await prisma.brand.findFirst({
    where: { organizationId: deps.organizationId, isDefault: true },
  });

  let weightsAdjusted = 0;
  let mixAdjusted = false;

  if (brand) {
    const currentWeights = brand.scoringWeights as Record<string, number>;
    const { weights, adjustments } = adjustScoringWeights(currentWeights, insights);

    const categoryLift: Record<string, number> = {};
    for (const insight of insights) {
      if (insight.dimension === 'category' && insight.sampleSize >= MIN_SAMPLE_SIZE) {
        categoryLift[insight.key] = insight.liftVsBaseline;
      }
    }

    const currentMix = brand.contentMix as Record<string, number>;
    const nextMix = Object.keys(categoryLift).length > 0
      ? adjustMixByPerformance(currentMix, categoryLift)
      : currentMix;
    mixAdjusted = JSON.stringify(nextMix) !== JSON.stringify(currentMix);

    if (adjustments.length > 0 || mixAdjusted) {
      await prisma.brand.update({
        where: { id: brand.id },
        data: { scoringWeights: weights, contentMix: nextMix },
      });
      weightsAdjusted = adjustments.length;

      // Recorded so a strategy shift is explainable weeks later, and reversible.
      await prisma.auditLog.create({
        data: {
          organizationId: deps.organizationId,
          actorType: 'system',
          action: 'learning_adjustment',
          subjectType: 'brand',
          subjectId: brand.id,
          // Serialized so Prisma's Json input type accepts the nested arrays.
          diff: JSON.parse(
            JSON.stringify({
              baseline,
              postsAnalyzed: posts.length,
              weightAdjustments: adjustments,
              mixBefore: currentMix,
              mixAfter: nextMix,
            }),
          ) as object,
        },
      });
    }

    for (const adjustment of adjustments) {
      log.info(adjustment, 'scoring weight adjusted');
    }
  }

  /* ---- memory: what worked, what the audience ignored ---- */

  for (const insight of insights) {
    if (insight.sampleSize < MIN_SAMPLE_SIZE) continue;
    const strong = insight.liftVsBaseline >= 1.2;
    const weak = insight.liftVsBaseline <= 0.7;
    if (!strong && !weak) continue;

    const memoryType = insight.dimension === 'hook_archetype'
      ? (strong ? 'successful_hook' : 'failed_hook')
      : (strong ? 'strong_topic' : 'weak_topic');

    await prisma.systemMemory.upsert({
      where: {
        organizationId_memoryType_key: {
          organizationId: deps.organizationId,
          memoryType,
          key: `${insight.dimension}:${insight.key}`,
        },
      },
      create: {
        organizationId: deps.organizationId,
        memoryType,
        key: `${insight.dimension}:${insight.key}`,
        value: { lift: insight.liftVsBaseline, sampleSize: insight.sampleSize },
        weight: insight.liftVsBaseline,
        observations: 1,
      },
      update: {
        value: { lift: insight.liftVsBaseline, sampleSize: insight.sampleSize },
        weight: insight.liftVsBaseline,
        observations: { increment: 1 },
        lastObservedAt: new Date(),
      },
    });
  }

  /* ---- posting hours, which the scheduler reads on the next cycle ---- */

  /**
   * Two representations, deliberately.
   *
   * computeInsights buckets hours into readable bands ("evening (17-21)"),
   * which is what a human wants to see. The scheduler needs an exact hour to
   * put on the calendar, so those are persisted separately under their own
   * dimension. Deriving one from the other is what caused them to disagree.
   */
  const rankedHours = optimalPostingHours(posts);
  const learnedHours = rankedHours.map((h) => h.hour);

  for (const hour of rankedHours) {
    await prisma.learningInsight.upsert({
      where: {
        organizationId_dimension_key_windowEnd: {
          organizationId: deps.organizationId,
          dimension: 'posting_hour_exact',
          key: String(hour.hour),
          windowEnd,
        },
      },
      create: {
        organizationId: deps.organizationId,
        dimension: 'posting_hour_exact',
        key: String(hour.hour),
        sampleSize: hour.sampleSize,
        avgEngagement: hour.avgScore,
        liftVsBaseline: baseline > 0 ? Number((hour.avgScore / baseline).toFixed(3)) : 1,
        confidence: Math.min(0.95, hour.sampleSize / 20),
        windowStart,
        windowEnd,
      },
      update: {
        sampleSize: hour.sampleSize,
        avgEngagement: hour.avgScore,
        liftVsBaseline: baseline > 0 ? Number((hour.avgScore / baseline).toFixed(3)) : 1,
      },
    });
    insightsWritten++;
  }

  await prisma.automationState.update({
    where: { organizationId: deps.organizationId },
    data: { lastLearningAt: new Date() },
  });

  log.info(
    { postsAnalyzed: posts.length, insightsWritten, weightsAdjusted, mixAdjusted, learnedHours },
    'learning cycle complete',
  );

  return {
    postsAnalyzed: posts.length,
    insightsWritten,
    weightsAdjusted,
    mixAdjusted,
    learnedPostingHours: learnedHours,
  };
}

/**
 * The posting hours the scheduler should use.
 *
 * Returns learned hours only once there is enough evidence to beat a sensible
 * default — the brief warns against fixed times forever, but guessing from
 * three posts is not an improvement on a default.
 */
export async function learnedPostingHours(organizationId: string): Promise<number[]> {
  const insights = await prisma.learningInsight.findMany({
    where: { organizationId, dimension: 'posting_hour_exact', sampleSize: { gte: 3 } },
    orderBy: [{ windowEnd: 'desc' }, { liftVsBaseline: 'desc' }],
    take: 8,
  });
  if (insights.length < 2) return [];

  const latestWindow = insights[0]?.windowEnd;
  return insights
    .filter((i) => i.windowEnd.getTime() === latestWindow?.getTime() && i.liftVsBaseline > 1)
    .map((i) => Number(i.key))
    .filter((hour) => Number.isInteger(hour) && hour >= 0 && hour <= 23)
    .slice(0, 4);
}
