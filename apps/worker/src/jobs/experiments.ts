/**
 * Experiment lifecycle.
 *
 * Assigns content to arms as it is generated, and evaluates running experiments
 * against measured performance. Reuses `performanceScore` from the learning
 * engine so an experiment and the learning cycle are judging content by the
 * same standard — an experiment that optimised for something else would pull
 * strategy in a different direction from the engine that consumes it.
 */
import { type Logger } from '@mmos/core';
import { prisma } from '@mmos/db';
import {
  analyzeExperiment,
  assignVariant,
  performanceScore,
  type ExperimentVariant,
  type PostPerformance,
} from '@mmos/agents';
import type { AutomationService } from '@mmos/engine';

export interface ExperimentDeps {
  organizationId: string;
  automation: AutomationService;
  logger: Logger;
}

/**
 * Finds the running experiment a new piece should join, if any.
 *
 * At most one experiment runs per organization at a time. Two concurrent
 * experiments would confound each other — a piece in the bold-hook arm of one
 * and the short-caption arm of another tells you nothing about either.
 */
export async function assignToExperiment(
  organizationId: string,
  contentPieceId: string,
  logger: Logger,
): Promise<{ experimentId: string; variant: string } | null> {
  const experiment = await prisma.experiment.findFirst({
    where: { organizationId, status: 'RUNNING' },
    orderBy: { startedAt: 'asc' },
  });
  if (!experiment) return null;

  const variants = experiment.variants as unknown as ExperimentVariant[];
  if (!Array.isArray(variants) || variants.length < 2) {
    logger.warn({ experimentId: experiment.id }, 'running experiment has no usable variants');
    return null;
  }

  const variant = assignVariant(experiment.id, contentPieceId, variants);
  await prisma.contentPiece.update({
    where: { id: contentPieceId },
    data: { experimentId: experiment.id, experimentVariant: variant },
  });

  logger.info({ experimentId: experiment.id, contentPieceId, variant }, 'assigned to experiment arm');
  return { experimentId: experiment.id, variant };
}

export interface EvaluationResult {
  experimentId: string;
  name: string;
  verdict: string;
  winner?: string;
  completed: boolean;
}

/**
 * Evaluates every running experiment.
 *
 * An experiment only completes when the statistics support a conclusion, or
 * when it has clearly run its course. Leaving one open indefinitely is better
 * than closing it on a difference that is not there.
 */
export async function evaluateExperiments(deps: ExperimentDeps): Promise<EvaluationResult[]> {
  await deps.automation.assertMayRun(deps.organizationId, 'learningEngine');

  const experiments = await prisma.experiment.findMany({
    where: { organizationId: deps.organizationId, status: 'RUNNING' },
  });

  const results: EvaluationResult[] = [];

  for (const experiment of experiments) {
    const variants = experiment.variants as unknown as ExperimentVariant[];
    if (!Array.isArray(variants) || variants.length < 2) continue;

    // Only published pieces with analytics can contribute an observation.
    const pieces = await prisma.contentPiece.findMany({
      where: {
        experimentId: experiment.id,
        experimentVariant: { not: null },
        publishingJobs: { some: { status: 'PUBLISHED' } },
      },
      include: {
        publishingJobs: {
          where: { status: 'PUBLISHED' },
          include: { analytics: { orderBy: { collectedAt: 'desc' }, take: 1 } },
        },
      },
    });

    const observations: Record<string, number[]> = {};
    for (const variant of variants) observations[variant.key] = [];

    for (const piece of pieces) {
      const job = piece.publishingJobs[0];
      const record = job?.analytics[0];
      if (!job?.publishedAt || !record) continue;

      const performance: PostPerformance = {
        contentPieceId: piece.id,
        category: piece.category,
        format: piece.format,
        ...(piece.hookArchetype ? { hookArchetype: piece.hookArchetype } : {}),
        postedAtHour: job.publishedAt.getUTCHours(),
        postedAtWeekday: job.publishedAt.getUTCDay(),
        views: record.views,
        reach: record.reach,
        likes: record.likes,
        comments: record.comments,
        shares: record.shares,
        saves: record.saves,
        avgWatchTimeSec: record.avgWatchTimeSec,
        followsGained: record.followsGained,
      };

      const score = performanceScore(performance);
      const arm = piece.experimentVariant;
      // A post with no reach denominator yields no comparable score, so it is
      // omitted rather than counted as a zero.
      if (score !== null && arm && observations[arm]) observations[arm]!.push(score);
    }

    const analysis = analyzeExperiment(observations, variants, experiment.minSampleSize);
    const complete = analysis.verdict === 'WINNER' || analysis.verdict === 'INCONCLUSIVE';

    await prisma.experiment.update({
      where: { id: experiment.id },
      data: {
        results: JSON.parse(JSON.stringify(analysis)) as object,
        conclusion: analysis.conclusion,
        winner: analysis.winner ?? null,
        ...(complete ? { status: 'COMPLETE', completedAt: new Date() } : {}),
      },
    });

    if (complete) {
      await prisma.auditLog.create({
        data: {
          organizationId: deps.organizationId,
          actorType: 'system',
          action: 'experiment_concluded',
          subjectType: 'experiment',
          subjectId: experiment.id,
          // Serialized so Prisma's Json input accepts the nested array.
          diff: JSON.parse(
            JSON.stringify({
              verdict: analysis.verdict,
              winner: analysis.winner ?? null,
              variants: analysis.variants,
            }),
          ) as object,
        },
      });

      // An inconclusive result is recorded, not acted on. Adopting the leading
      // arm anyway is exactly the mistake the test is there to prevent.
      if (analysis.verdict === 'WINNER') {
        await recordWinnerToMemory(deps.organizationId, experiment.variable, analysis.winner as string, analysis);
      }
    }

    deps.logger.info(
      {
        experimentId: experiment.id,
        verdict: analysis.verdict,
        winner: analysis.winner,
        samples: Object.fromEntries(Object.entries(observations).map(([k, v]) => [k, v.length])),
      },
      'experiment evaluated',
    );

    results.push({
      experimentId: experiment.id,
      name: experiment.name,
      verdict: analysis.verdict,
      ...(analysis.winner ? { winner: analysis.winner } : {}),
      completed: complete,
    });
  }

  return results;
}

/**
 * Writes a confirmed winner into system memory.
 *
 * Memory is what later cycles read, so this is how an experiment actually
 * changes behaviour rather than just producing a report nobody acts on.
 */
async function recordWinnerToMemory(
  organizationId: string,
  variable: string,
  winner: string,
  analysis: ReturnType<typeof analyzeExperiment>,
): Promise<void> {
  await prisma.systemMemory.upsert({
    where: {
      organizationId_memoryType_key: {
        organizationId,
        memoryType: 'experiment_result',
        key: `${variable}:${winner}`,
      },
    },
    create: {
      organizationId,
      memoryType: 'experiment_result',
      key: `${variable}:${winner}`,
      value: {
        variable,
        winner,
        lift: analysis.comparison?.lift ?? 1,
        conclusion: analysis.conclusion,
      },
      weight: analysis.comparison?.lift ?? 1,
    },
    update: {
      value: {
        variable,
        winner,
        lift: analysis.comparison?.lift ?? 1,
        conclusion: analysis.conclusion,
      },
      weight: analysis.comparison?.lift ?? 1,
      observations: { increment: 1 },
      lastObservedAt: new Date(),
    },
  });
}
