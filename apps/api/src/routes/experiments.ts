/**
 * Experiment management.
 *
 * The single-variable rule and the sample floor are enforced here rather than
 * left to the caller, because an experiment that changes two things produces a
 * result nobody can act on.
 */
import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { NotFoundError, ValidationError } from '@mmos/core';
import { prisma } from '@mmos/db';
import { EXPERIMENT_VARIABLES, validateExperiment } from '@mmos/agents';
import type { AppContext } from '../context.js';
import { orgScope, requireAuth } from '../auth.js';

const variantSchema = z.object({
  key: z.string().min(1).max(40),
  description: z.string().min(1).max(200),
});

export async function experimentRoutes(app: FastifyInstance, _ctx: AppContext): Promise<void> {
  app.get('/experiments', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const experiments = await prisma.experiment.findMany({
      where: scope,
      include: { _count: { select: { contentPieces: true } } },
      orderBy: [{ status: 'asc' }, { createdAt: 'desc' }],
      take: 50,
    });
    return { experiments, testableVariables: EXPERIMENT_VARIABLES };
  });

  app.post('/experiments', { preHandler: requireAuth('EDITOR') }, async (request, reply) => {
    const scope = orgScope(request);
    const body = z
      .object({
        name: z.string().min(1).max(120),
        hypothesis: z.string().min(1).max(2000),
        variable: z.enum(EXPERIMENT_VARIABLES),
        variants: z.array(variantSchema).min(2).max(4),
        minSampleSize: z.number().int().min(5).max(200).default(10),
      })
      .parse(request.body);

    // Throws on a violation of the single-variable or sample-floor rules.
    validateExperiment(body);

    const experiment = await prisma.experiment.create({
      data: {
        organizationId: scope.organizationId,
        name: body.name,
        hypothesis: body.hypothesis,
        variable: body.variable,
        variants: body.variants,
        minSampleSize: body.minSampleSize,
        status: 'DRAFT',
      },
    });

    return reply.code(201).send({ experiment });
  });

  app.post('/experiments/:id/start', { preHandler: requireAuth('EDITOR') }, async (request, reply) => {
    const scope = orgScope(request);
    const { id } = z.object({ id: z.string() }).parse(request.params);

    const experiment = await prisma.experiment.findFirst({ where: { id, ...scope } });
    if (!experiment) throw new NotFoundError('Experiment', id);
    if (experiment.status !== 'DRAFT') {
      throw new ValidationError(`Experiment is ${experiment.status} and cannot be started.`);
    }

    // Concurrent experiments confound each other: a piece in the bold-hook arm
    // of one and the short-caption arm of another tells you nothing about either.
    const running = await prisma.experiment.findFirst({
      where: { ...scope, status: 'RUNNING' },
    });
    if (running) {
      return reply.code(409).send({
        error: 'ExperimentAlreadyRunning',
        code: 'CONFLICT',
        message: `"${running.name}" is already running. Concurrent experiments confound each other, so finish or abandon it first.`,
      });
    }

    const started = await prisma.experiment.update({
      where: { id },
      data: { status: 'RUNNING', startedAt: new Date() },
    });

    await prisma.auditLog.create({
      data: {
        organizationId: scope.organizationId,
        actorType: 'user',
        actorId: request.user!.id,
        action: 'experiment_started',
        subjectType: 'experiment',
        subjectId: id,
      },
    });

    return { experiment: started };
  });

  app.post('/experiments/:id/abandon', { preHandler: requireAuth('EDITOR') }, async (request) => {
    const scope = orgScope(request);
    const { id } = z.object({ id: z.string() }).parse(request.params);

    const experiment = await prisma.experiment.findFirst({ where: { id, ...scope } });
    if (!experiment) throw new NotFoundError('Experiment', id);

    const updated = await prisma.experiment.update({
      where: { id },
      data: {
        status: 'ABANDONED',
        completedAt: new Date(),
        conclusion: experiment.conclusion ?? 'Abandoned before reaching a conclusion.',
      },
    });
    return { experiment: updated };
  });

  /** Full detail, including which pieces landed in which arm. */
  app.get('/experiments/:id', { preHandler: requireAuth() }, async (request) => {
    const scope = orgScope(request);
    const { id } = z.object({ id: z.string() }).parse(request.params);

    const experiment = await prisma.experiment.findFirst({
      where: { id, ...scope },
      include: {
        contentPieces: {
          select: {
            id: true,
            title: true,
            status: true,
            experimentVariant: true,
            publishingJobs: {
              select: { status: true, publishedAt: true },
            },
          },
        },
      },
    });
    if (!experiment) throw new NotFoundError('Experiment', id);
    return { experiment };
  });
}
