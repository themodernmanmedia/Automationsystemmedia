/**
 * Worker process.
 *
 * Runs the autonomous loop, the publishing worker, and the periodic jobs.
 * Every scheduled task begins by checking the kill switch, so stopping the
 * system stops it everywhere and not just at the API.
 */
import { Worker } from 'bullmq';
import { getConfig, createLogger, ForbiddenError, type Logger } from '@mmos/core';
import { prisma, TokenStore, disconnect } from '@mmos/db';
import { AdapterRegistry } from '@mmos/platforms';
import { AiOrchestrator, createLlmProvider, createSearchProviders, createVoiceProvider, createImageProvider, type ImageProvider, type LlmProvider, type SearchProvider, type VoiceProvider } from '@mmos/ai';
import {
  AnalyticsService, AutomationService, DbCostSink, PublishingService,
  QUEUE_NAMES, QueueRegistry, assessQueueHealth, distributePostTimes,
} from '@mmos/engine';
import { createPublishingWorker, reconcileScheduledJobs, refreshExpiringTokens } from './jobs/publishing.js';
import { runResearch, runTopicScoring, runTrendScan, type PipelineDeps } from './jobs/pipeline.js';
import { generateFromTopic } from './jobs/generation.js';
import { renderPendingReels } from './jobs/reel-render.js';
import { ReelCompositor } from '@mmos/media';
import { S3StorageProvider, type StorageProvider } from '@mmos/ai';

const config = getConfig();
const logger = createLogger({
  level: config.LOG_LEVEL,
  name: 'mmos-worker',
  pretty: config.NODE_ENV === 'development',
});

const queues = new QueueRegistry(config.REDIS_URL);
const tokens = new TokenStore(config.ENCRYPTION_KEY);
const adapters = new AdapterRegistry(config);
const automation = new AutomationService(logger);
const publishing = new PublishingService({ adapters, tokens, automation, logger });
const analytics = new AnalyticsService({ adapters, tokens, logger });

let llm: LlmProvider | null = null;
let searchProviders: SearchProvider[] = [];
try {
  llm = createLlmProvider(config);
} catch (err) {
  logger.warn({ err }, 'no LLM provider configured; content generation is disabled');
}
try {
  searchProviders = createSearchProviders(config);
} catch (err) {
  logger.warn({ err }, 'no research provider configured; trend discovery is disabled');
}

// Storage is a hard requirement for Instagram, which fetches media from a
// public URL. Without it, slides are designed but cannot be published.
let storage: StorageProvider | null = null;
try {
  storage = new S3StorageProvider({
    ...(config.S3_ENDPOINT ? { endpoint: config.S3_ENDPOINT } : {}),
    region: config.S3_REGION,
    ...(config.S3_BUCKET ? { bucket: config.S3_BUCKET } : {}),
    ...(config.S3_ACCESS_KEY_ID ? { accessKeyId: config.S3_ACCESS_KEY_ID } : {}),
    ...(config.S3_SECRET_ACCESS_KEY ? { secretAccessKey: config.S3_SECRET_ACCESS_KEY } : {}),
    ...(config.S3_PUBLIC_BASE_URL ? { publicBaseUrl: config.S3_PUBLIC_BASE_URL } : {}),
  });
} catch (err) {
  logger.warn({ err }, 'object storage is not configured; rendered media cannot be published');
}

// Reels need a voice provider. Without one they are written but cannot be
// rendered, and the render job says so rather than emitting a silent video.
let voice: VoiceProvider | null = null;
try {
  voice = createVoiceProvider(config);
} catch (err) {
  logger.warn({ err }, 'no voice provider configured; Reels cannot be rendered');
}

// Optional. Without it, beats render on the brand background, which is a
// legitimate editorial look rather than a degraded one.
let image: ImageProvider | null = null;
try {
  image = createImageProvider(config);
} catch {
  logger.info('no image provider configured; reel beats will use the brand background');
}

const compositor = new ReelCompositor({
  ffmpegPath: config.FFMPEG_PATH,
  ffprobePath: config.FFPROBE_PATH,
  workDir: config.RENDER_WORK_DIR,
  logger,
});

function pipelineDeps(organizationId: string): PipelineDeps {
  if (!llm) throw new Error('No LLM provider configured');
  return {
    organizationId,
    orchestrator: new AiOrchestrator({
      llm,
      costSink: new DbCostSink(organizationId),
      logger,
      dailyLimitUsd: config.DAILY_COST_LIMIT_USD,
      monthlyLimitUsd: config.MONTHLY_COST_LIMIT_USD,
    }),
    searchProviders,
    automation,
    logger,
  };
}

/**
 * The autonomous loop.
 *
 * Deliberately demand-driven rather than a fixed production schedule: it scans
 * for topics on a cadence but only generates content when the queue is actually
 * short. The brief is explicit that more content does not mean better growth,
 * so producing to a quota would be the wrong design.
 */
async function autonomousTick(organizationId: string): Promise<void> {
  const log = logger.child({ organizationId, loop: 'autonomous' });

  let state;
  try {
    state = await automation.assertMayRun(organizationId);
  } catch (err) {
    if (err instanceof ForbiddenError) {
      log.info({ reason: err.message }, 'autonomous tick skipped');
      return;
    }
    throw err;
  }

  if (!state.autonomousMode) {
    log.debug('autonomous mode is off; nothing to do');
    return;
  }

  const scheduled = await prisma.publishingJob.findMany({
    where: { socialAccount: { organizationId }, status: { in: ['QUEUED', 'SCHEDULED'] } },
    select: { scheduledAt: true },
  });
  const health = assessQueueHealth(scheduled.map((j) => j.scheduledAt), state);
  log.info({ health }, 'queue health');

  if (!llm || searchProviders.length === 0) {
    log.warn('autonomous mode is on but generation providers are unavailable; skipping generation');
    return;
  }

  const deps = pipelineDeps(organizationId);

  // Scan hourly regardless of queue depth: a breaking story is worth knowing
  // about even when the backlog is full, since it may displace weaker content.
  const lastScan = state.lastTrendScanAt?.getTime() ?? 0;
  if (Date.now() - lastScan > 3_600_000) {
    try {
      const found = await runTrendScan(deps);
      await prisma.automationState.update({
        where: { organizationId },
        data: { lastTrendScanAt: new Date() },
      });
      log.info({ found }, 'trend scan finished');
    } catch (err) {
      log.error({ err }, 'trend scan failed');
    }
  }

  try {
    const scored = await runTopicScoring(deps);
    if (scored > 0) log.info({ scored }, 'topics scored');
  } catch (err) {
    log.error({ err }, 'topic scoring failed');
  }

  // Research and generation are the expensive stages, so they run only when
  // the queue is actually short rather than to a fixed production quota.
  if (health.shouldGenerate) {
    const wanted = Math.min(3, Math.max(1, health.postsNeeded));

    const selected = await prisma.topic.findMany({
      where: { organizationId, status: 'SELECTED' },
      orderBy: { compositeScore: 'desc' },
      take: wanted,
    });

    for (const topic of selected) {
      try {
        const result = await runResearch(deps, topic.id);
        log.info({ topicId: topic.id, ...result }, 'research complete');
      } catch (err) {
        log.error({ err, topicId: topic.id }, 'research failed');
        await prisma.topic.update({ where: { id: topic.id }, data: { status: 'REJECTED' } }).catch(() => {});
      }
    }

    // Generate from topics whose research survived fact checking.
    const researched = await prisma.topic.findMany({
      where: { organizationId, status: 'RESEARCHED' },
      orderBy: { compositeScore: 'desc' },
      take: wanted,
    });

    const accounts = await prisma.socialAccount.findMany({
      where: { organizationId, status: 'CONNECTED' },
      select: { id: true },
    });

    for (const topic of researched) {
      try {
        const result = await generateFromTopic(
          { organizationId, orchestrator: deps.orchestrator, storage, automation, logger,
            chromiumPath: process.env['CHROMIUM_PATH'] ?? undefined },
          topic.id,
        );
        log.info(result, 'content generated');

        // Only approved content is scheduled. Flagged pieces wait for a human
        // in the exception queue rather than going out unattended.
        if (result.status === 'APPROVED' && accounts.length > 0) {
          const [slot] = distributePostTimes(1, new Date(Date.now() + 3_600_000));
          await publishing.schedule({
            organizationId,
            contentPieceId: result.contentPieceId,
            socialAccountIds: accounts.map((a) => a.id),
            ...(slot ? { scheduledAt: slot } : {}),
          });
          log.info({ contentPieceId: result.contentPieceId, scheduledAt: slot }, 'content scheduled');
        }
      } catch (err) {
        log.error({ err, topicId: topic.id }, 'generation failed');
      }
    }
  }

  await prisma.automationState.update({
    where: { organizationId },
    data: { lastGenerationAt: new Date() },
  });
}

/** Runs a task for every organization, isolating failures to one tenant. */
async function forEachOrganization(
  taskName: string,
  task: (organizationId: string) => Promise<void>,
  onlyOrganizationId?: string,
): Promise<void> {
  const organizations = onlyOrganizationId
    ? [{ id: onlyOrganizationId }]
    : await prisma.organization.findMany({ select: { id: true } });
  for (const org of organizations) {
    try {
      await task(org.id);
    } catch (err) {
      logger.error({ err, organizationId: org.id, task: taskName }, 'scheduled task failed');
    }
  }
}

async function main(): Promise<void> {
  logger.info(
    { queues: Object.values(QUEUE_NAMES), llm: llm?.name ?? 'none', search: searchProviders.map((p) => p.name) },
    'Modern Man OS worker starting',
  );

  const publishWorker = createPublishingWorker({ connection: queues.connection, publishing, logger });

  // Generic worker for the loop and periodic maintenance queues.
  const loopWorker = new Worker(
    QUEUE_NAMES.autonomousLoop,
    async (job) => {
      // Present when a human triggered this from the dashboard; absent for the
      // scheduled run, which covers every organization.
      const only = (job.data as { organizationId?: string } | undefined)?.organizationId;

      switch (job.name) {
        case 'tick':
          await forEachOrganization('autonomous-tick', autonomousTick, only);
          return;
        case 'render':
          await forEachOrganization('reel-render', async (organizationId) => {
            await automation.assertMayRun(organizationId, 'reelProducer');
            const result = await renderPendingReels({
              organizationId, voice, image, storage, compositor, logger,
              recordCost: async (entry) => {
                await new DbCostSink(organizationId).record({ ...entry, provider: entry.provider });
              },
            });
            if (result.rendered > 0 || result.failed > 0) {
              logger.info({ organizationId, ...result }, 'reel render pass complete');
            }
          }, only);
          return;
        case 'analytics':
          await forEachOrganization('analytics', async (organizationId) => {
            await automation.assertMayRun(organizationId, 'analytics');
            const result = await analytics.collectForOrganization(organizationId);
            logger.info({ organizationId, ...result }, 'analytics collected');
          }, only);
          return;
        case 'snapshot':
          await forEachOrganization('snapshot', async (organizationId) => {
            const count = await analytics.snapshotAccounts(organizationId);
            logger.info({ organizationId, count }, 'account snapshots captured');
          }, only);
          return;
        case 'tokens':
          await refreshExpiringTokens({ tokens, adapters, logger }).then((r) =>
            logger.info(r, 'token refresh pass complete'),
          );
          return;
        case 'reconcile':
          await reconcileScheduledJobs(queues, logger);
          return;
        default:
          logger.warn({ name: job.name }, 'unknown loop job');
      }
    },
    { connection: queues.connection, concurrency: 1 },
  );

  loopWorker.on('failed', (job, err) => {
    logger.error({ jobName: job?.name, err }, 'loop job failed');
  });

  // Repeatable schedules. Cadences follow the brief: hourly trend scanning,
  // frequent analytics, daily snapshots.
  const loopQueue = queues.get(QUEUE_NAMES.autonomousLoop);
  await loopQueue.add('tick', {}, { repeat: { pattern: '*/15 * * * *' }, jobId: 'repeat-tick' });
  await loopQueue.add('render', {}, { repeat: { pattern: '*/10 * * * *' }, jobId: 'repeat-render' });
  await loopQueue.add('analytics', {}, { repeat: { pattern: '0 */2 * * *' }, jobId: 'repeat-analytics' });
  await loopQueue.add('snapshot', {}, { repeat: { pattern: '0 3 * * *' }, jobId: 'repeat-snapshot' });
  await loopQueue.add('tokens', {}, { repeat: { pattern: '0 * * * *' }, jobId: 'repeat-tokens' });
  await loopQueue.add('reconcile', {}, { repeat: { pattern: '*/30 * * * *' }, jobId: 'repeat-reconcile' });

  // On boot, re-arm every timer from the database. This is what makes a Redis
  // loss survivable: the intent was never stored only in Redis.
  await reconcileScheduledJobs(queues, logger);

  const shutdown = async (signal: string) => {
    logger.info({ signal }, 'worker shutting down');
    await publishWorker.close();
    await loopWorker.close();
    await queues.close();
    await disconnect();
    process.exit(0);
  };
  process.on('SIGTERM', () => void shutdown('SIGTERM'));
  process.on('SIGINT', () => void shutdown('SIGINT'));

  logger.info('worker ready');
}

main().catch((err) => {
  logger.fatal({ err }, 'worker failed to start');
  process.exit(1);
});
