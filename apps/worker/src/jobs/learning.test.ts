/**
 * Learning cycle — integration test against real Postgres.
 *
 * The behaviours worth guarding are the safety rails, not the happy path: that
 * a thin sample changes nothing, that a single anomalous week cannot collapse
 * the strategy, and that every adjustment is explainable afterwards.
 */
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { createLogger, DEFAULT_CONTENT_MIX, DEFAULT_SCORING_WEIGHTS } from '@mmos/core';
import { prisma } from '@mmos/db';
import { AutomationService } from '@mmos/engine';
import { runLearningCycle, learnedPostingHours } from './learning.js';

const logger = createLogger({ level: 'silent' });
const automation = new AutomationService(logger);

let organizationId: string;
let brandId: string;
let socialAccountId: string;

async function seedPost(options: {
  category: string;
  format?: 'CAROUSEL' | 'REEL';
  hookArchetype?: string;
  saves: number;
  reach?: number;
  hour?: number;
}) {
  const piece = await prisma.contentPiece.create({
    data: {
      organizationId,
      brandId,
      format: options.format ?? 'CAROUSEL',
      status: 'PUBLISHED',
      category: options.category as never,
      title: `Post about ${options.category}`,
      hook: 'A hook',
      ...(options.hookArchetype ? { hookArchetype: options.hookArchetype } : {}),
    },
  });

  const publishedAt = new Date(Date.UTC(2026, 0, 15, options.hour ?? 9, 0, 0));
  const job = await prisma.publishingJob.create({
    data: {
      contentPieceId: piece.id,
      socialAccountId,
      platform: 'INSTAGRAM',
      status: 'PUBLISHED',
      scheduledAt: publishedAt,
      publishedAt,
      platformPostId: `post-${piece.id}`,
      idempotencyKey: `learn-${piece.id}`,
    },
  });

  await prisma.analyticsRecord.create({
    data: {
      socialAccountId,
      publishingJobId: job.id,
      platform: 'INSTAGRAM',
      platformPostId: job.platformPostId!,
      reach: options.reach ?? 10_000,
      views: options.reach ?? 10_000,
      likes: 100,
      comments: 10,
      shares: 10,
      saves: options.saves,
      followsGained: 5,
    },
  });
  return piece;
}

beforeAll(async () => {
  const org = await prisma.organization.create({
    data: { name: 'Learning Test Org', slug: `learn-test-${Date.now()}` },
  });
  organizationId = org.id;

  const brand = await prisma.brand.create({
    data: {
      organizationId,
      name: 'Test Brand',
      colors: {}, fonts: {}, aspectRatios: {},
      contentMix: DEFAULT_CONTENT_MIX,
      scoringWeights: DEFAULT_SCORING_WEIGHTS,
      isDefault: true,
    },
  });
  brandId = brand.id;

  const account = await prisma.socialAccount.create({
    data: {
      organizationId,
      platform: 'INSTAGRAM',
      platformAccountId: 'ig-learn-test',
      username: 'learntest',
      status: 'CONNECTED',
    },
  });
  socialAccountId = account.id;

  await automation.get(organizationId); // creates the automation state row
});

afterEach(async () => {
  // Cascades clear the posts, jobs, and analytics between cases.
  await prisma.contentPiece.deleteMany({ where: { organizationId } });
  await prisma.learningInsight.deleteMany({ where: { organizationId } });
  await prisma.systemMemory.deleteMany({ where: { organizationId } });
  await prisma.brand.update({
    where: { id: brandId },
    data: { scoringWeights: DEFAULT_SCORING_WEIGHTS, contentMix: DEFAULT_CONTENT_MIX },
  });
});

afterAll(async () => {
  await prisma.organization.deleteMany({ where: { id: organizationId } });
  await prisma.$disconnect();
});

describe('sample-size floor', () => {
  it('changes nothing when there is too little data to justify it', async () => {
    for (let i = 0; i < 3; i++) await seedPost({ category: 'AI', saves: 500 });

    const result = await runLearningCycle({ organizationId, automation, logger });

    expect(result.postsAnalyzed).toBe(3);
    expect(result.skippedReason).toMatch(/minimum sample/);
    expect(result.weightsAdjusted).toBe(0);
    expect(result.insightsWritten).toBe(0);

    // Three lucky posts must not be able to rewrite strategy.
    const brand = await prisma.brand.findUnique({ where: { id: brandId } });
    expect(brand!.scoringWeights).toEqual(DEFAULT_SCORING_WEIGHTS);
    expect(brand!.contentMix).toEqual(DEFAULT_CONTENT_MIX);
  });
});

describe('insights', () => {
  it('records which categories outperform and which do not', async () => {
    for (let i = 0; i < 8; i++) await seedPost({ category: 'AI', saves: 400 });
    for (let i = 0; i < 8; i++) await seedPost({ category: 'LIFESTYLE', saves: 5 });

    const result = await runLearningCycle({ organizationId, automation, logger });
    expect(result.postsAnalyzed).toBe(16);
    expect(result.insightsWritten).toBeGreaterThan(0);

    const ai = await prisma.learningInsight.findFirst({
      where: { organizationId, dimension: 'category', key: 'AI' },
    });
    const lifestyle = await prisma.learningInsight.findFirst({
      where: { organizationId, dimension: 'category', key: 'LIFESTYLE' },
    });

    expect(ai!.liftVsBaseline).toBeGreaterThan(1);
    expect(lifestyle!.liftVsBaseline).toBeLessThan(1);
    expect(ai!.sampleSize).toBe(8);
  });

  it('remembers strong and weak performers so they inform later cycles', async () => {
    for (let i = 0; i < 8; i++) await seedPost({ category: 'AI', hookArchetype: 'number-lead', saves: 400 });
    for (let i = 0; i < 8; i++) await seedPost({ category: 'LIFESTYLE', hookArchetype: 'question', saves: 2 });

    await runLearningCycle({ organizationId, automation, logger });

    const memories = await prisma.systemMemory.findMany({ where: { organizationId } });
    const types = memories.map((m) => m.memoryType);
    expect(types).toContain('successful_hook');
    expect(types).toContain('failed_hook');
    expect(memories.find((m) => m.key === 'hook_archetype:number-lead')!.memoryType).toBe('successful_hook');
  });
});

describe('strategy adjustment', () => {
  it('shifts the content mix toward what performs, within bounds', async () => {
    for (let i = 0; i < 10; i++) await seedPost({ category: 'AI', saves: 600 });
    for (let i = 0; i < 10; i++) await seedPost({ category: 'LIFESTYLE', saves: 2 });

    const before = (await prisma.brand.findUnique({ where: { id: brandId } }))!
      .contentMix as Record<string, number>;

    const result = await runLearningCycle({ organizationId, automation, logger });
    expect(result.mixAdjusted).toBe(true);

    const after = (await prisma.brand.findUnique({ where: { id: brandId } }))!
      .contentMix as Record<string, number>;

    expect(after['AI']!).toBeGreaterThan(before['AI']!);
    expect(after['LIFESTYLE']!).toBeLessThan(before['LIFESTYLE']!);

    // Still a valid distribution — a mix that does not total 100 would skew
    // the planner silently.
    const total = Object.values(after).reduce((a, b) => a + b, 0);
    expect(total).toBeCloseTo(100, 1);

    // Bounded: one strong week cannot collapse the account into one category.
    for (const key of Object.keys(before)) {
      expect(Math.abs(after[key]! - before[key]!)).toBeLessThan(8);
    }
  });

  it('writes an audit record so a strategy shift is explainable later', async () => {
    for (let i = 0; i < 10; i++) await seedPost({ category: 'AI', saves: 600 });
    for (let i = 0; i < 10; i++) await seedPost({ category: 'SPORTS', saves: 2 });

    await runLearningCycle({ organizationId, automation, logger });

    const log = await prisma.auditLog.findFirst({
      where: { organizationId, action: 'learning_adjustment' },
      orderBy: { createdAt: 'desc' },
    });
    expect(log).toBeTruthy();
    const diff = log!.diff as Record<string, unknown>;
    expect(diff['postsAnalyzed']).toBe(20);
    expect(diff).toHaveProperty('mixBefore');
    expect(diff).toHaveProperty('mixAfter');
  });
});

describe('posting hours', () => {
  it('feeds measured best hours back into scheduling', async () => {
    for (let i = 0; i < 6; i++) await seedPost({ category: 'AI', saves: 500, hour: 18 });
    for (let i = 0; i < 6; i++) await seedPost({ category: 'AI', saves: 3, hour: 3 });

    const result = await runLearningCycle({ organizationId, automation, logger });
    expect(result.learnedPostingHours).toContain(18);

    // The scheduler reads this; only above-baseline hours are returned.
    const hours = await learnedPostingHours(organizationId);
    expect(hours).toContain(18);
    expect(hours).not.toContain(3);
  });

  it('returns nothing when the evidence is too thin to beat a default', async () => {
    for (let i = 0; i < 6; i++) await seedPost({ category: 'AI', saves: 100, hour: 12 });
    await runLearningCycle({ organizationId, automation, logger });

    // A single hour is not a schedule; guessing here is no better than the default.
    expect(await learnedPostingHours(organizationId)).toEqual([]);
  });
});

describe('kill switch', () => {
  it('does not run while automation is halted', async () => {
    for (let i = 0; i < 10; i++) await seedPost({ category: 'AI', saves: 400 });
    await automation.setKillSwitch(organizationId, true, 'test');

    await expect(runLearningCycle({ organizationId, automation, logger })).rejects.toThrow(/Kill switch/);

    await automation.setKillSwitch(organizationId, false, 'test');
  });
});
