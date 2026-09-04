/**
 * Experiment lifecycle — integration test against real Postgres.
 *
 * The behaviours that matter: an experiment must not conclude from noise, an
 * inconclusive result must be recorded rather than acted on, and a confirmed
 * winner must reach system memory, since memory is what later cycles read.
 */
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { createLogger } from '@mmos/core';
import { prisma } from '@mmos/db';
import { AutomationService } from '@mmos/engine';
import { assignToExperiment, evaluateExperiments } from './experiments.js';

const logger = createLogger({ level: 'silent' });
const automation = new AutomationService(logger);

let organizationId: string;
let socialAccountId: string;

const VARIANTS = [
  { key: 'number_lead', description: 'Open with the statistic' },
  { key: 'contrarian', description: 'Open by contradicting a belief' },
];

async function createExperiment(minSampleSize = 5, status: 'RUNNING' | 'DRAFT' = 'RUNNING') {
  return prisma.experiment.create({
    data: {
      organizationId,
      name: 'Hook style',
      hypothesis: 'Number-led hooks save better',
      variable: 'hook',
      variants: VARIANTS,
      minSampleSize,
      status,
      startedAt: new Date(),
    },
  });
}

/** Creates a published piece in a given arm with a given performance level. */
async function publishedPiece(experimentId: string, variant: string, saves: number) {
  const piece = await prisma.contentPiece.create({
    data: {
      organizationId,
      format: 'CAROUSEL',
      status: 'PUBLISHED',
      category: 'BUSINESS',
      title: `Piece ${variant} ${saves}`,
      hook: 'hook',
      experimentId,
      experimentVariant: variant,
    },
  });
  const publishedAt = new Date(Date.now() - 86_400_000);
  const job = await prisma.publishingJob.create({
    data: {
      contentPieceId: piece.id,
      socialAccountId,
      platform: 'INSTAGRAM',
      status: 'PUBLISHED',
      scheduledAt: publishedAt,
      publishedAt,
      platformPostId: `post-${piece.id}`,
      idempotencyKey: `exp-${piece.id}`,
    },
  });
  await prisma.analyticsRecord.create({
    data: {
      socialAccountId,
      publishingJobId: job.id,
      platform: 'INSTAGRAM',
      platformPostId: job.platformPostId!,
      reach: 10_000,
      views: 10_000,
      likes: 100,
      comments: 10,
      shares: 10,
      saves,
      followsGained: 5,
    },
  });
  return piece;
}

beforeAll(async () => {
  const org = await prisma.organization.create({
    data: { name: 'Experiment Org', slug: `exp-${Date.now()}` },
  });
  organizationId = org.id;
  const account = await prisma.socialAccount.create({
    data: {
      organizationId,
      platform: 'INSTAGRAM',
      platformAccountId: 'ig-exp',
      username: 'exptest',
      status: 'CONNECTED',
    },
  });
  socialAccountId = account.id;
  await automation.get(organizationId);
});

afterEach(async () => {
  await prisma.contentPiece.deleteMany({ where: { organizationId } });
  await prisma.experiment.deleteMany({ where: { organizationId } });
  await prisma.systemMemory.deleteMany({ where: { organizationId } });
});

afterAll(async () => {
  await prisma.organization.deleteMany({ where: { id: organizationId } });
  await prisma.$disconnect();
});

describe('assignment', () => {
  it('assigns a new piece to the running experiment', async () => {
    const experiment = await createExperiment();
    const piece = await prisma.contentPiece.create({
      data: {
        organizationId, format: 'CAROUSEL', status: 'WRITING',
        category: 'BUSINESS', title: 'New piece', hook: 'hook',
      },
    });

    const assignment = await assignToExperiment(organizationId, piece.id, logger);
    expect(assignment!.experimentId).toBe(experiment.id);
    expect(VARIANTS.map((v) => v.key)).toContain(assignment!.variant);

    const stored = await prisma.contentPiece.findUnique({ where: { id: piece.id } });
    expect(stored!.experimentVariant).toBe(assignment!.variant);
  });

  it('assigns nothing when no experiment is running', async () => {
    await createExperiment(5, 'DRAFT');
    const piece = await prisma.contentPiece.create({
      data: {
        organizationId, format: 'CAROUSEL', status: 'WRITING',
        category: 'BUSINESS', title: 'Unassigned', hook: 'hook',
      },
    });
    expect(await assignToExperiment(organizationId, piece.id, logger)).toBeNull();
  });
});

describe('evaluation', () => {
  it('keeps collecting until each arm meets the sample floor', async () => {
    const experiment = await createExperiment(5);
    for (let i = 0; i < 3; i++) await publishedPiece(experiment.id, 'number_lead', 300);
    for (let i = 0; i < 2; i++) await publishedPiece(experiment.id, 'contrarian', 50);

    const [result] = await evaluateExperiments({ organizationId, automation, logger });
    expect(result!.verdict).toBe('COLLECTING');
    expect(result!.completed).toBe(false);

    // Still running, so more content keeps flowing into it.
    const stored = await prisma.experiment.findUnique({ where: { id: experiment.id } });
    expect(stored!.status).toBe('RUNNING');
  });

  it('declares a winner when the arms genuinely separate', async () => {
    const experiment = await createExperiment(5);
    // Wide, consistent separation.
    for (const saves of [400, 420, 380, 410, 390]) {
      await publishedPiece(experiment.id, 'number_lead', saves);
    }
    for (const saves of [40, 45, 38, 42, 41]) {
      await publishedPiece(experiment.id, 'contrarian', saves);
    }

    const [result] = await evaluateExperiments({ organizationId, automation, logger });
    expect(result!.verdict).toBe('WINNER');
    expect(result!.winner).toBe('number_lead');

    const stored = await prisma.experiment.findUnique({ where: { id: experiment.id } });
    expect(stored!.status).toBe('COMPLETE');
    expect(stored!.winner).toBe('number_lead');
    expect(stored!.conclusion).toMatch(/95% confidence/);

    // A winner must reach memory, since memory is what later cycles read.
    const memory = await prisma.systemMemory.findFirst({
      where: { organizationId, memoryType: 'experiment_result' },
    });
    expect(memory!.key).toBe('hook:number_lead');
  });

  it('records an inconclusive result without adopting the leading arm', async () => {
    const experiment = await createExperiment(5);
    // Overlapping spreads: a difference that is not really there.
    for (const saves of [100, 300, 150, 250, 200]) {
      await publishedPiece(experiment.id, 'number_lead', saves);
    }
    for (const saves of [120, 280, 140, 260, 190]) {
      await publishedPiece(experiment.id, 'contrarian', saves);
    }

    const [result] = await evaluateExperiments({ organizationId, automation, logger });
    expect(result!.verdict).toBe('INCONCLUSIVE');
    expect(result!.winner).toBeUndefined();

    const stored = await prisma.experiment.findUnique({ where: { id: experiment.id } });
    expect(stored!.status).toBe('COMPLETE');
    expect(stored!.winner).toBeNull();

    // Critically: nothing was written to memory, so nothing changes strategy.
    const memory = await prisma.systemMemory.findMany({
      where: { organizationId, memoryType: 'experiment_result' },
    });
    expect(memory).toEqual([]);
  });

  it('ignores pieces with no reach, rather than scoring them as zero', async () => {
    const experiment = await createExperiment(5);
    for (let i = 0; i < 5; i++) await publishedPiece(experiment.id, 'number_lead', 300);
    for (let i = 0; i < 5; i++) await publishedPiece(experiment.id, 'contrarian', 50);

    // One extra post with no reach denominator: it must not count as a 0.
    const piece = await publishedPiece(experiment.id, 'contrarian', 0);
    await prisma.analyticsRecord.updateMany({
      where: { publishingJob: { contentPieceId: piece.id } },
      data: { reach: null, views: null },
    });

    const [result] = await evaluateExperiments({ organizationId, automation, logger });
    const stored = await prisma.experiment.findUnique({ where: { id: experiment.id } });
    const results = stored!.results as { variants: Array<{ key: string; sampleSize: number }> };
    const contrarian = results.variants.find((v) => v.key === 'contrarian');

    // Five usable observations, not six.
    expect(contrarian!.sampleSize).toBe(5);
    expect(result!.verdict).not.toBe('COLLECTING');
  });

  it('does not run while the kill switch is engaged', async () => {
    await createExperiment();
    await automation.setKillSwitch(organizationId, true, 'test');
    await expect(evaluateExperiments({ organizationId, automation, logger })).rejects.toThrow(/Kill switch/);
    await automation.setKillSwitch(organizationId, false, 'test');
  });
});
