/**
 * Automation control center, including the emergency controls.
 *
 * The brief requires the system never be able to make itself impossible to
 * stop. These endpoints are therefore the plainest in the codebase: no
 * queueing, no async indirection, no conditional logic that could be subtly
 * wrong. A stop control that depends on clever code is not a stop control.
 */
import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { prisma } from '@mmos/db';
import { QUEUE_NAMES, assessQueueHealth } from '@mmos/engine';
import { capabilityMatrix, PLANNED_PLATFORMS, SUPPORTED_PLATFORMS } from '@mmos/platforms';
import type { AppContext } from '../context.js';
import { orgScope, requireAuth } from '../auth.js';

export async function automationRoutes(app: FastifyInstance, ctx: AppContext): Promise<void> {
  app.get('/automation', { preHandler: requireAuth() }, async (request) => {
    const { organizationId } = orgScope(request);
    const state = await ctx.automation.get(organizationId);

    const scheduled = await prisma.publishingJob.findMany({
      where: { socialAccount: { organizationId }, status: { in: ['QUEUED', 'SCHEDULED'] } },
      select: { scheduledAt: true },
    });

    const queue = assessQueueHealth(
      scheduled.map((j) => j.scheduledAt),
      {
        minQueueHours: state.minQueueHours,
        targetQueueHours: state.targetQueueHours,
        maxQueueHours: state.maxQueueHours,
        maxPostsPerDay: state.maxPostsPerDay,
      },
    );

    // Agent status is derived from real run records, never invented.
    const recentRuns = await prisma.agentRun.findMany({
      where: { organizationId, startedAt: { gte: new Date(Date.now() - 24 * 3_600_000) } },
      orderBy: { startedAt: 'desc' },
      take: 200,
    });

    const agents = Object.keys(state.agentFlags).map((key) => {
      const runs = recentRuns.filter((r) => r.agentName === toSnake(key));
      const latest = runs[0];
      const status = !state.agentFlags[key]
        ? 'PAUSED'
        : latest?.status === 'RUNNING'
          ? 'RUNNING'
          : latest?.status === 'FAILED'
            ? 'ERROR'
            : 'IDLE';
      return {
        key,
        enabled: state.agentFlags[key] ?? false,
        status,
        lastRunAt: latest?.startedAt ?? null,
        runsLast24h: runs.length,
        failuresLast24h: runs.filter((r) => r.status === 'FAILED').length,
      };
    });

    return {
      state,
      queue,
      agents,
      integrations: ctx.integrations,
      integrationErrors: ctx.integrationErrors,
    };
  });

  /* ------------------------- emergency controls ------------------------- */

  app.post('/automation/kill', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const { organizationId } = orgScope(request);
    const { engaged } = z.object({ engaged: z.boolean() }).parse(request.body);
    await ctx.automation.setKillSwitch(organizationId, engaged, request.user!.id);
    return { killSwitch: engaged };
  });

  app.post('/automation/publishing', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const { organizationId } = orgScope(request);
    const { paused } = z.object({ paused: z.boolean() }).parse(request.body);
    await ctx.automation.setPublishingPaused(organizationId, paused, request.user!.id);
    return { publishingPaused: paused };
  });

  app.post('/automation/autonomous', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const { organizationId } = orgScope(request);
    const { enabled } = z.object({ enabled: z.boolean() }).parse(request.body);

    // Autonomous mode without a working LLM would spin producing nothing but
    // errors, so refuse rather than let it look enabled.
    if (enabled && !ctx.integrations.llm) {
      return {
        error: 'Cannot enable autonomous mode: no LLM provider is configured.',
        detail: ctx.integrationErrors['llm'],
      };
    }

    await ctx.automation.setAutonomousMode(organizationId, enabled, request.user!.id);
    return { autonomousMode: enabled };
  });

  app.post('/automation/agents/:key', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const { organizationId } = orgScope(request);
    const { key } = z.object({ key: z.string() }).parse(request.params);
    const { enabled } = z.object({ enabled: z.boolean() }).parse(request.body);
    await ctx.automation.setAgentEnabled(organizationId, key, enabled, request.user!.id);
    return { agent: key, enabled };
  });

  app.post('/automation/queue/clear', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const { organizationId } = orgScope(request);
    const cancelled = await ctx.publishing.clearQueue(organizationId, request.user!.id);
    return { cancelledJobs: cancelled };
  });

  app.post('/automation/config', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const { organizationId } = orgScope(request);
    const body = z
      .object({
        minQueueHours: z.number().int().min(1).max(720).optional(),
        targetQueueHours: z.number().int().min(1).max(720).optional(),
        maxQueueHours: z.number().int().min(1).max(720).optional(),
        maxPostsPerDay: z.number().int().min(1).max(50).optional(),
      })
      .parse(request.body);

    const updated = await prisma.automationState.update({ where: { organizationId }, data: body });
    return { state: updated };
  });

  /* --------------------------- manual triggers -------------------------- */

  /**
   * Runs a pipeline stage immediately.
   *
   * This exists so an operator can see what the system actually produces
   * before trusting it to run unattended. Without it, the only way to generate
   * anything would be to enable autonomous mode and hope.
   *
   * The job is enqueued rather than run inline: it is the same code path the
   * scheduler uses, so a manual run cannot behave differently from a scheduled
   * one, and a long generation does not block the request.
   */
  app.post('/automation/run/:job', { preHandler: requireAuth('EDITOR') }, async (request, reply) => {
    const { organizationId } = orgScope(request);
    const { job } = z
      .object({ job: z.enum(['tick', 'render', 'analytics', 'snapshot', 'reconcile']) })
      .parse(request.params);

    if (!ctx.queues) {
      return reply.code(503).send({
        error: 'QueueUnavailable',
        code: 'API_ERROR',
        message: 'Cannot reach the job queue. Check that Redis is running and REDIS_URL is correct.',
      });
    }

    // The kill switch outranks a manual trigger. Someone stopping the system
    // must not be overridden by another operator pressing Run now.
    const state = await ctx.automation.get(organizationId);
    if (state.killSwitch) {
      return reply.code(409).send({
        error: 'KillSwitchEngaged',
        code: 'FORBIDDEN',
        message: 'The kill switch is engaged. Release it before running jobs.',
      });
    }

    if (job === 'tick' && !ctx.integrations.llm) {
      return reply.code(422).send({
        error: 'NotConfigured',
        code: 'PROVIDER_NOT_CONFIGURED',
        message: ctx.integrationErrors['llm'] ?? 'No LLM provider is configured.',
      });
    }

    const queued = await ctx.queues.get(QUEUE_NAMES.autonomousLoop).add(
      job,
      { organizationId },
      {
        // A distinct id per request, so pressing the button twice genuinely
        // runs twice rather than being silently deduplicated.
        jobId: `manual-${job}-${organizationId}-${Date.now()}`,
        removeOnComplete: { count: 50 },
      },
    );

    await prisma.auditLog.create({
      data: {
        organizationId,
        actorType: 'user',
        actorId: request.user!.id,
        action: 'manual_run',
        subjectType: 'job',
        subjectId: job,
      },
    });

    return { queued: true, job, jobId: queued.id };
  });

  /**
   * Requeues failed publishing jobs.
   *
   * Deliberately refuses to retry an auth failure: the token is dead, so
   * retrying consumes platform rate limit and cannot succeed. Those accounts
   * are named in the response so the operator reconnects them instead.
   */
  app.post('/automation/publishing/retry', { preHandler: requireAuth('EDITOR') }, async (request, reply) => {
    const { organizationId } = orgScope(request);

    if (!ctx.queues) {
      return reply.code(503).send({
        error: 'QueueUnavailable',
        code: 'API_ERROR',
        message: 'Cannot reach the job queue. Check that Redis is running.',
      });
    }

    const failed = await prisma.publishingJob.findMany({
      where: { socialAccount: { organizationId }, status: 'FAILED' },
      include: { socialAccount: { select: { username: true, platform: true } } },
      take: 50,
    });

    const requeued: string[] = [];
    const skipped: Array<{ jobId: string; account: string; reason: string }> = [];

    for (const job of failed) {
      if (job.lastErrorCode === 'AUTH_ERROR') {
        skipped.push({
          jobId: job.id,
          account: `${job.socialAccount.platform} @${job.socialAccount.username}`,
          reason: 'Credentials are invalid. Reconnect the account; retrying cannot succeed.',
        });
        continue;
      }
      if (job.lastErrorCode === 'CAPABILITY_NOT_SUPPORTED') {
        skipped.push({
          jobId: job.id,
          account: `${job.socialAccount.platform} @${job.socialAccount.username}`,
          reason: 'The platform API does not support this operation. Retrying cannot succeed.',
        });
        continue;
      }

      await prisma.publishingJob.update({
        where: { id: job.id },
        data: { status: 'SCHEDULED', lastError: null, lastErrorCode: null, scheduledAt: new Date() },
      });
      await ctx.queues.get(QUEUE_NAMES.publishing).add(
        'publish',
        { publishingJobId: job.id },
        { jobId: `publish-retry-${job.id}-${Date.now()}` },
      );
      requeued.push(job.id);
    }

    await prisma.auditLog.create({
      data: {
        organizationId,
        actorType: 'user',
        actorId: request.user!.id,
        action: 'retry_failed_publishing',
        diff: { requeued: requeued.length, skipped: skipped.length },
      },
    });

    return { requeued: requeued.length, skipped };
  });

  /**
   * The capability matrix, served to the dashboard so it can render
   * `NOT SUPPORTED BY CURRENT API` with the real reason instead of showing a
   * control that would throw.
   */
  app.get('/platforms/capabilities', { preHandler: requireAuth() }, async () => {
    return {
      matrix: capabilityMatrix(),
      supported: SUPPORTED_PLATFORMS,
      planned: PLANNED_PLATFORMS,
      configured: ctx.adapters.configured(),
    };
  });
}

/** Agent flags are camelCase; AgentRun.agentName is snake_case. */
function toSnake(key: string): string {
  return key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
}
