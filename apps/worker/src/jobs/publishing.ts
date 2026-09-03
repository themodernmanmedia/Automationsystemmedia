/**
 * Publishing worker and the schedule reconciler.
 *
 * The reconciler is the reason a scheduled Instagram post survives
 * infrastructure failure. Postgres holds the intent; Redis holds only the
 * timer. On boot — and periodically after — every job that should have a timer
 * gets one re-armed from the database. A wiped Redis costs punctuality, not the
 * post itself.
 */
import { Worker, type Job } from 'bullmq';
import type { Redis } from 'ioredis';
import { type Logger } from '@mmos/core';
import { prisma } from '@mmos/db';
import type { PublishingService } from '@mmos/engine';
import { PUBLISH_JOB_OPTIONS, QUEUE_NAMES, type QueueRegistry } from '../queues.js';

export interface PublishJobData {
  publishingJobId: string;
}

export function createPublishingWorker(deps: {
  connection: Redis;
  publishing: PublishingService;
  logger: Logger;
}): Worker<PublishJobData> {
  return new Worker<PublishJobData>(
    QUEUE_NAMES.publishing,
    async (job: Job<PublishJobData>) => {
      const result = await deps.publishing.execute(job.data.publishingJobId);
      return {
        platformPostId: result.platformPostId,
        restrictedVisibility: result.restrictedVisibility ?? false,
      };
    },
    {
      connection: deps.connection,
      // Kept low deliberately: publishing concurrently to the same account is
      // how you trip a platform rate limit and get the account restricted.
      concurrency: 2,
      limiter: { max: 10, duration: 60_000 },
    },
  )
    .on('completed', (job, result) => {
      deps.logger.info({ jobId: job.id, result }, 'publish complete');
    })
    .on('failed', (job, err) => {
      deps.logger.error({ jobId: job?.id, err, attempts: job?.attemptsMade }, 'publish failed');
    });
}

/**
 * Re-arms Redis timers from the database.
 *
 * Idempotent: BullMQ jobs are keyed by the publishing job id, so re-running
 * this never produces a duplicate post. Runs at boot and on a schedule.
 */
export async function reconcileScheduledJobs(
  queues: QueueRegistry,
  logger: Logger,
  lookaheadMs = 7 * 86_400_000,
): Promise<{ armed: number; overdue: number }> {
  const horizon = new Date(Date.now() + lookaheadMs);

  const jobs = await prisma.publishingJob.findMany({
    where: {
      status: { in: ['QUEUED', 'SCHEDULED'] },
      scheduledAt: { lte: horizon },
      // DELEGATED jobs are Facebook's responsibility once accepted, so we do
      // not arm a timer for them.
      scheduleStrategy: { not: 'DELEGATED' },
    },
    select: { id: true, scheduledAt: true },
  });

  const queue = queues.get(QUEUE_NAMES.publishing);
  let armed = 0;
  let overdue = 0;

  for (const job of jobs) {
    const delay = Math.max(0, job.scheduledAt.getTime() - Date.now());
    if (delay === 0) overdue++;

    await queue.add(
      'publish',
      { publishingJobId: job.id },
      {
        ...PUBLISH_JOB_OPTIONS,
        // The deterministic id is what makes re-arming safe to repeat.
        jobId: `publish:${job.id}`,
        delay,
      },
    );
    armed++;
  }

  if (overdue > 0) {
    logger.warn(
      { overdue },
      'found overdue publishing jobs; they will publish now, late. The worker was likely down at their scheduled time.',
    );
  }
  logger.info({ armed, overdue }, 'reconciled scheduled publishing jobs');
  return { armed, overdue };
}

/**
 * Refreshes platform tokens before they expire, with lead time.
 *
 * TikTok access tokens last only ~24h, so this is not optional maintenance —
 * without it, scheduled TikTok posts fail with an auth error the next day.
 */
export async function refreshExpiringTokens(deps: {
  tokens: import('@mmos/db').TokenStore;
  adapters: import('@mmos/platforms').AdapterRegistry;
  logger: Logger;
}): Promise<{ refreshed: number; failed: number }> {
  // Six hours of lead time: enough for several retry cycles before expiry.
  const accountIds = await deps.tokens.findExpiring(6 * 3_600_000);
  let refreshed = 0;
  let failed = 0;

  for (const accountId of accountIds) {
    try {
      const account = await prisma.socialAccount.findUnique({ where: { id: accountId } });
      const stored = await deps.tokens.get(accountId);
      if (!account || !stored) continue;

      const adapter = deps.adapters.get(account.platform as never);
      // Meta re-exchanges the long-lived token; TikTok uses a refresh token.
      const tokens = await adapter.refreshToken(stored.refreshToken ?? stored.accessToken);

      await deps.tokens.store({
        socialAccountId: accountId,
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken ?? null,
        expiresAt: tokens.expiresAt ?? null,
        refreshExpiresAt: tokens.refreshExpiresAt ?? null,
        scopes: tokens.scopes,
      });
      await prisma.socialAccount.update({
        where: { id: accountId },
        data: { status: 'CONNECTED', statusMessage: null },
      });
      refreshed++;
    } catch (err) {
      failed++;
      const failures = await deps.tokens.recordRefreshFailure(accountId).catch(() => 0);
      deps.logger.error({ err, accountId, failures }, 'token refresh failed');

      // After repeated failures the token is genuinely dead; mark the account
      // so the dashboard prompts a reconnect instead of failing silently.
      if (failures >= 3) {
        await prisma.socialAccount.update({
          where: { id: accountId },
          data: {
            status: 'TOKEN_EXPIRED',
            statusMessage: 'Token refresh failed repeatedly. Reconnect this account.',
          },
        });
      }
    }
  }

  return { refreshed, failed };
}
