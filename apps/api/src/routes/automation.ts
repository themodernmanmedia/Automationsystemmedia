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
import { assessQueueHealth } from '@mmos/engine';
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
