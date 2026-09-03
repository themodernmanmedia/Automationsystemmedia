import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { NotFoundError } from '@mmos/core';
import { prisma } from '@mmos/db';
import { allowedTransitions, assertTransition, type ContentStatus } from '@mmos/contracts';
import { DbCostSink } from '@mmos/engine';
import type { AppContext } from '../context.js';
import { orgScope, requireAuth } from '../auth.js';

export async function contentRoutes(app: FastifyInstance, ctx: AppContext): Promise<void> {
  app.get('/content', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const query = z
      .object({
        status: z.string().optional(),
        format: z.string().optional(),
        limit: z.coerce.number().int().min(1).max(100).default(25),
        cursor: z.string().optional(),
      })
      .parse(request.query);

    const pieces = await prisma.contentPiece.findMany({
      where: {
        ...scope,
        ...(query.status ? { status: query.status as never } : {}),
        ...(query.format ? { format: query.format as never } : {}),
      },
      include: {
        topic: { select: { id: true, title: true, compositeScore: true } },
        carousel: { select: { slideCount: true } },
        reel: { select: { durationSec: true, renderStatus: true } },
        publishingJobs: {
          select: { id: true, platform: true, status: true, scheduledAt: true, platformUrl: true },
        },
        _count: { select: { qaResults: true } },
      },
      orderBy: { createdAt: 'desc' },
      take: query.limit,
      ...(query.cursor ? { cursor: { id: query.cursor }, skip: 1 } : {}),
    });

    return {
      items: pieces,
      nextCursor: pieces.length === query.limit ? pieces[pieces.length - 1]?.id : null,
    };
  });

  /**
   * Full provenance for one piece: topic, sources, claims, QA results, publish
   * attempts, analytics, and cost. This is the traceability the brief requires
   * — for any published post, everything that produced it.
   */
  app.get('/content/:id', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const { id } = z.object({ id: z.string() }).parse(request.params);

    const piece = await prisma.contentPiece.findFirst({
      where: { id, ...scope },
      include: {
        topic: {
          include: {
            sources: true,
            claims: { orderBy: { verification: 'asc' } },
            researchReports: true,
          },
        },
        carousel: { include: { slides: { orderBy: { position: 'asc' } } } },
        reel: { include: { audioAssets: true } },
        captions: true,
        mediaAssets: true,
        qaResults: { orderBy: { createdAt: 'desc' } },
        scores: true,
        statusHistory: { orderBy: { createdAt: 'asc' } },
        publishingJobs: {
          include: {
            attempts: { orderBy: { createdAt: 'desc' } },
            analytics: { orderBy: { collectedAt: 'desc' }, take: 1 },
            socialAccount: { select: { platform: true, username: true } },
          },
        },
      },
    });
    if (!piece) throw new NotFoundError('ContentPiece', id);

    const costUsd = await new DbCostSink(scope.organizationId).costOfContentPiece(id);

    return {
      content: piece,
      costUsd,
      allowedTransitions: allowedTransitions(piece.status as ContentStatus),
    };
  });

  /** Manual approval, for exception-queue items and non-autonomous operation. */
  app.post('/content/:id/approve', { preHandler: requireAuth('EDITOR') }, async (request) => {
    const scope = orgScope(request);
    const { id } = z.object({ id: z.string() }).parse(request.params);

    const piece = await prisma.contentPiece.findFirst({ where: { id, ...scope } });
    if (!piece) throw new NotFoundError('ContentPiece', id);

    // Throws on an illegal move, so approval cannot skip the pipeline.
    assertTransition(piece.status as ContentStatus, 'APPROVED');

    await prisma.contentPiece.update({
      where: { id },
      data: {
        status: 'APPROVED',
        approvedAt: new Date(),
        approvedBy: request.user!.id,
        flagReason: null,
      },
    });
    await prisma.contentStatusChange.create({
      data: {
        contentPieceId: id,
        fromStatus: piece.status,
        toStatus: 'APPROVED',
        actor: request.user!.id,
        reason: 'Manually approved',
      },
    });

    return { ok: true, status: 'APPROVED' };
  });

  app.post('/content/:id/schedule', { preHandler: requireAuth('EDITOR') }, async (request) => {
    const scope = orgScope(request);
    const { id } = z.object({ id: z.string() }).parse(request.params);
    const body = z
      .object({ socialAccountIds: z.array(z.string()).min(1), scheduledAt: z.coerce.date().optional() })
      .parse(request.body);

    const jobs = await ctx.publishing.schedule({
      organizationId: scope.organizationId,
      contentPieceId: id,
      socialAccountIds: body.socialAccountIds,
      ...(body.scheduledAt ? { scheduledAt: body.scheduledAt } : {}),
    });

    return {
      jobs: jobs.map((j) => ({
        id: j.id,
        platform: j.platform,
        scheduledAt: j.scheduledAt,
        // Shows which platform is doing the waiting.
        strategy: j.scheduleStrategy,
      })),
    };
  });

  app.post('/content/:id/archive', { preHandler: requireAuth('EDITOR') }, async (request) => {
    const scope = orgScope(request);
    const { id } = z.object({ id: z.string() }).parse(request.params);
    const piece = await prisma.contentPiece.findFirst({ where: { id, ...scope } });
    if (!piece) throw new NotFoundError('ContentPiece', id);

    assertTransition(piece.status as ContentStatus, 'ARCHIVED');
    await prisma.contentPiece.update({ where: { id }, data: { status: 'ARCHIVED' } });
    return { ok: true };
  });

  /** The exception queue — everything autonomous mode declined to publish. */
  app.get('/content/flagged', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const items = await prisma.contentPiece.findMany({
      where: { ...scope, status: 'FLAGGED' },
      include: {
        qaResults: { where: { verdict: 'FAIL' } },
        topic: { select: { title: true } },
      },
      orderBy: { flaggedAt: 'desc' },
      take: 50,
    });
    return { items };
  });
}
