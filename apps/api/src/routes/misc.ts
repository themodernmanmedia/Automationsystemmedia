/**
 * Accounts, analytics, topics, brand, cost, logs, and health.
 */
import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { NotFoundError, DEFAULT_BRAND, DEFAULT_CONTENT_MIX, DEFAULT_SCORING_WEIGHTS, BRAND_COLORS } from '@mmos/core';
import { healthcheck, prisma } from '@mmos/db';
import { getCapabilities, type PlatformName } from '@mmos/platforms';
import { DbCostSink } from '@mmos/engine';
import type { AppContext } from '../context.js';
import { orgScope, requireAuth } from '../auth.js';

export async function miscRoutes(app: FastifyInstance, ctx: AppContext): Promise<void> {
  /* ------------------------------- health ------------------------------- */

  app.get('/health', async (_request, reply) => {
    const db = await healthcheck();
    const ok = db.ok;
    return reply.code(ok ? 200 : 503).send({
      status: ok ? 'healthy' : 'degraded',
      checks: { database: db },
      integrations: ctx.integrations,
      integrationErrors: ctx.integrationErrors,
      version: '0.1.0',
      uptimeSec: Math.floor(process.uptime()),
    });
  });

  /* ------------------------------ accounts ------------------------------ */

  app.get('/accounts', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const accounts = await prisma.socialAccount.findMany({
      where: scope,
      include: {
        // Selected explicitly: token MATERIAL must never leave the server.
        token: { select: { expiresAt: true, refreshExpiresAt: true, lastRefreshedAt: true, refreshFailures: true } },
        _count: { select: { publishingJobs: true } },
      },
      orderBy: { createdAt: 'asc' },
    });

    return {
      accounts: accounts.map((a) => {
        const caps = getCapabilities(a.platform as PlatformName);
        const expiresAt = a.token?.expiresAt ?? null;
        const tokenStatus = !a.token
          ? 'MISSING'
          : expiresAt && expiresAt < new Date()
            ? 'EXPIRED'
            : expiresAt && expiresAt.getTime() - Date.now() < 7 * 86_400_000
              ? 'EXPIRING'
              : 'VALID';

        return {
          id: a.id,
          platform: a.platform,
          username: a.username,
          displayName: a.displayName,
          profileImageUrl: a.profileImageUrl,
          accountType: a.accountType,
          status: a.status,
          statusMessage: a.statusMessage,
          followerCount: a.followerCount,
          scopes: a.scopes,
          lastSyncAt: a.lastSyncAt,
          lastPublishAt: a.lastPublishAt,
          lastPublishError: a.lastPublishError,
          postCount: a._count.publishingJobs,
          tokenStatus,
          tokenExpiresAt: expiresAt,
          // TikTok's audit state materially changes what publishing means, so
          // it is surfaced on the card rather than buried in docs.
          isAudited: a.isAudited,
          auditWarning:
            a.platform === 'TIKTOK' && !a.isAudited
              ? 'AUDIT PENDING — posts published through the API will be private (SELF_ONLY) until TikTok approves this client.'
              : null,
          capabilities: caps
            ? {
                canSchedule: caps.canSchedule,
                scheduleStrategy: caps.scheduleStrategy,
                canDelete: caps.canDelete,
                canPostCarousel: caps.canPostCarousel,
                canPostVideo: caps.canPostVideo,
                notes: caps.notes,
              }
            : null,
        };
      }),
    };
  });

  app.patch('/accounts/:id', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const scope = orgScope(request);
    const { id } = z.object({ id: z.string() }).parse(request.params);
    const body = z.object({ isAudited: z.boolean().optional(), brandId: z.string().nullable().optional() }).parse(request.body);

    const account = await prisma.socialAccount.findFirst({ where: { id, ...scope } });
    if (!account) throw new NotFoundError('SocialAccount', id);

    const updated = await prisma.socialAccount.update({ where: { id }, data: body });
    return { account: { id: updated.id, isAudited: updated.isAudited } };
  });

  /* ------------------------------ analytics ----------------------------- */

  app.get('/analytics/summary', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const { days } = z.object({ days: z.coerce.number().int().min(1).max(365).default(30) }).parse(request.query);
    const since = new Date(Date.now() - days * 86_400_000);

    const summary = await ctx.analytics.summary(scope.organizationId, since);

    const topContent = await prisma.analyticsRecord.findMany({
      where: { socialAccount: scope, collectedAt: { gte: since } },
      orderBy: { engagementRate: 'desc' },
      take: 10,
      include: {
        publishingJob: {
          include: { contentPiece: { select: { id: true, title: true, format: true, category: true } } },
        },
      },
    });

    const snapshots = await prisma.performanceSnapshot.findMany({
      where: { socialAccount: scope, capturedAt: { gte: since } },
      orderBy: { capturedAt: 'asc' },
    });

    return { ...summary, topContent, followerHistory: snapshots };
  });

  /* -------------------------------- topics ------------------------------ */

  app.get('/topics', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const query = z
      .object({
        status: z.string().optional(),
        limit: z.coerce.number().int().min(1).max(100).default(50),
      })
      .parse(request.query);

    const topics = await prisma.topic.findMany({
      where: { ...scope, ...(query.status ? { status: query.status as never } : {}) },
      include: { _count: { select: { sources: true, claims: true, contentPieces: true } } },
      orderBy: [{ compositeScore: 'desc' }, { createdAt: 'desc' }],
      take: query.limit,
    });
    return { topics };
  });

  /* --------------------------------- brand ------------------------------ */

  app.get('/brand', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const brand = await prisma.brand.findFirst({ where: { ...scope, isDefault: true } });
    return {
      brand,
      defaults: {
        colors: BRAND_COLORS,
        fonts: DEFAULT_BRAND.fonts,
        tone: DEFAULT_BRAND.tone,
        avoid: DEFAULT_BRAND.avoid,
        contentMix: DEFAULT_CONTENT_MIX,
        scoringWeights: DEFAULT_SCORING_WEIGHTS,
      },
    };
  });

  app.patch('/brand/:id', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const scope = orgScope(request);
    const { id } = z.object({ id: z.string() }).parse(request.params);
    const body = z
      .object({
        name: z.string().optional(),
        logoUrl: z.string().url().nullable().optional(),
        colors: z.record(z.string()).optional(),
        fonts: z.record(z.string()).optional(),
        tone: z.array(z.string()).optional(),
        avoidList: z.array(z.string()).optional(),
        ctaStyle: z.string().optional(),
        defaultSlideCount: z.number().int().min(3).max(10).optional(),
        contentMix: z.record(z.number()).optional(),
        scoringWeights: z.record(z.number()).optional(),
      })
      .parse(request.body);

    const brand = await prisma.brand.findFirst({ where: { id, ...scope } });
    if (!brand) throw new NotFoundError('Brand', id);

    // A mix that does not sum to 100 would silently skew the content planner.
    if (body.contentMix) {
      const total = Object.values(body.contentMix).reduce((a, b) => a + b, 0);
      if (Math.abs(total - 100) > 0.5) {
        return { error: `Content mix must total 100%, but the supplied values total ${total.toFixed(1)}%.` };
      }
    }

    const updated = await prisma.brand.update({ where: { id }, data: body });
    await prisma.auditLog.create({
      data: {
        organizationId: scope.organizationId,
        actorType: 'user',
        actorId: request.user!.id,
        action: 'brand_updated',
        subjectType: 'brand',
        subjectId: id,
        diff: body,
      },
    });
    return { brand: updated };
  });

  /* --------------------------------- cost ------------------------------- */

  app.get('/cost', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const { days } = z.object({ days: z.coerce.number().int().min(1).max(90).default(30) }).parse(request.query);
    const sink = new DbCostSink(scope.organizationId);
    const since = new Date(Date.now() - days * 86_400_000);

    const [today, month, breakdown] = await Promise.all([
      sink.spentToday(),
      sink.spentThisMonth(),
      sink.breakdown(since),
    ]);

    return {
      dailySpent: Number(today.toFixed(4)),
      dailyLimit: ctx.config.DAILY_COST_LIMIT_USD,
      monthlySpent: Number(month.toFixed(4)),
      monthlyLimit: ctx.config.MONTHLY_COST_LIMIT_USD,
      halted: today >= ctx.config.DAILY_COST_LIMIT_USD || month >= ctx.config.MONTHLY_COST_LIMIT_USD,
      breakdown,
    };
  });

  /* --------------------------------- logs ------------------------------- */

  app.get('/logs/agents', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const { limit } = z.object({ limit: z.coerce.number().int().min(1).max(200).default(50) }).parse(request.query);
    const runs = await prisma.agentRun.findMany({
      where: scope,
      include: { errors: true },
      orderBy: { startedAt: 'desc' },
      take: limit,
    });
    return { runs };
  });

  app.get('/logs/audit', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const scope = orgScope(request);
    const { limit } = z.object({ limit: z.coerce.number().int().min(1).max(200).default(50) }).parse(request.query);
    const logs = await prisma.auditLog.findMany({
      where: scope,
      orderBy: { createdAt: 'desc' },
      take: limit,
    });
    return { logs };
  });

  app.get('/logs/publishing', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const jobs = await prisma.publishingJob.findMany({
      where: { socialAccount: scope },
      include: {
        attempts: { orderBy: { createdAt: 'desc' }, take: 3 },
        socialAccount: { select: { platform: true, username: true } },
        contentPiece: { select: { id: true, title: true, format: true } },
      },
      orderBy: { updatedAt: 'desc' },
      take: 50,
    });
    return { jobs };
  });

  /* ------------------------------- calendar ----------------------------- */

  /**
   * Publishing jobs in a date range, for the calendar.
   *
   * Distinct from /logs/publishing, which shows recent activity regardless of
   * when it was scheduled. A calendar needs the opposite: everything landing in
   * a window, including future work that has not run yet.
   */
  app.get('/calendar', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const query = z
      .object({ from: z.coerce.date().optional(), to: z.coerce.date().optional() })
      .parse(request.query);

    const from = query.from ?? new Date(Date.now() - 7 * 86_400_000);
    const to = query.to ?? new Date(Date.now() + 14 * 86_400_000);

    const jobs = await prisma.publishingJob.findMany({
      where: {
        socialAccount: scope,
        scheduledAt: { gte: from, lte: to },
        status: { not: 'CANCELLED' },
      },
      include: {
        socialAccount: { select: { platform: true, username: true } },
        contentPiece: {
          select: { id: true, title: true, hook: true, format: true, category: true, status: true },
        },
      },
      orderBy: { scheduledAt: 'asc' },
      take: 500,
    });

    return {
      from,
      to,
      jobs: jobs.map((job) => ({
        id: job.id,
        scheduledAt: job.scheduledAt,
        publishedAt: job.publishedAt,
        status: job.status,
        platform: job.platform,
        username: job.socialAccount.username,
        platformUrl: job.platformUrl,
        lastError: job.lastError,
        // Shows which side is doing the waiting: DELEGATED means the platform
        // holds it, SELF_TIMED means this system must be up at that moment.
        scheduleStrategy: job.scheduleStrategy,
        content: job.contentPiece,
      })),
    };
  });

  /* ------------------------------- overview ----------------------------- */

  app.get('/overview', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const dayAgo = new Date(Date.now() - 86_400_000);
    const weekAgo = new Date(Date.now() - 7 * 86_400_000);

    const [publishedToday, queued, failed, flagged, accounts, state, topTopics] = await Promise.all([
      prisma.publishingJob.count({
        where: { socialAccount: scope, status: 'PUBLISHED', publishedAt: { gte: dayAgo } },
      }),
      prisma.publishingJob.count({
        where: { socialAccount: scope, status: { in: ['QUEUED', 'SCHEDULED'] } },
      }),
      prisma.publishingJob.count({
        where: { socialAccount: scope, status: 'FAILED', updatedAt: { gte: weekAgo } },
      }),
      prisma.contentPiece.count({ where: { ...scope, status: 'FLAGGED' } }),
      prisma.socialAccount.findMany({
        where: { ...scope, status: 'CONNECTED' },
        select: { platform: true, username: true, followerCount: true },
      }),
      ctx.automation.get(scope.organizationId),
      prisma.topic.findMany({
        where: { ...scope, status: { in: ['SCORED', 'SELECTED'] } },
        orderBy: { compositeScore: 'desc' },
        take: 5,
        select: { id: true, title: true, category: true, compositeScore: true, isBreakingNews: true },
      }),
    ]);

    const analytics = await ctx.analytics.summary(scope.organizationId, weekAgo);

    return {
      today: { published: publishedToday, queued, failed, flagged },
      accounts,
      followers: accounts.reduce((sum, a) => sum + (a.followerCount ?? 0), 0),
      weekAnalytics: analytics.totals,
      trendingTopics: topTopics,
      automation: {
        autonomousMode: state.autonomousMode,
        killSwitch: state.killSwitch,
        publishingPaused: state.publishingPaused,
      },
      integrations: ctx.integrations,
    };
  });
}
