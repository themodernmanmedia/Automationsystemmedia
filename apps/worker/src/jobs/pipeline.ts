/**
 * Content pipeline jobs.
 *
 * Each stage is an independently retryable job rather than one long function,
 * so a failure at fact-checking does not discard the research that preceded it.
 * State lives in the database between stages, which is also what makes the
 * pipeline resumable after a worker restart.
 */
import { type Logger } from '@mmos/core';
import { prisma } from '@mmos/db';
import type { AiOrchestrator, SearchProvider } from '@mmos/ai';
import {
  FactCheckerAgent,
  ResearcherAgent,
  TopicScorerAgent,
  TrendHunterAgent,
  type AgentContext,
  type AgentRunSink,
} from '@mmos/agents';
import type { AutomationService } from '@mmos/engine';

/** Persists agent runs so the dashboard's agent panel shows real activity. */
export class DbRunSink implements AgentRunSink {
  constructor(private readonly organizationId: string) {}

  async record(run: {
    agentName: string;
    status: 'SUCCESS' | 'FAILED';
    itemsProcessed: number;
    itemsProduced: number;
    durationMs: number;
    error?: { code: string; message: string; retryable: boolean };
    outputSummary?: unknown;
  }): Promise<void> {
    const created = await prisma.agentRun.create({
      data: {
        organizationId: this.organizationId,
        agentName: run.agentName,
        status: run.status,
        trigger: 'schedule',
        itemsProcessed: run.itemsProcessed,
        itemsProduced: run.itemsProduced,
        durationMs: run.durationMs,
        finishedAt: new Date(),
        outputSummary: run.outputSummary ? JSON.parse(JSON.stringify(run.outputSummary)) : undefined,
      },
    });

    if (run.error) {
      await prisma.agentError.create({
        data: {
          agentRunId: created.id,
          errorCode: run.error.code,
          message: run.error.message,
          retryable: run.error.retryable,
        },
      });
    }
  }
}

export interface PipelineDeps {
  organizationId: string;
  orchestrator: AiOrchestrator;
  searchProviders: SearchProvider[];
  automation: AutomationService;
  logger: Logger;
}

function agentContext(deps: PipelineDeps): AgentContext {
  return {
    organizationId: deps.organizationId,
    orchestrator: deps.orchestrator,
    logger: deps.logger,
    runSink: new DbRunSink(deps.organizationId),
  };
}

/** Discovers topics and persists them with their sources. */
export async function runTrendScan(deps: PipelineDeps, maxTopics = 10): Promise<number> {
  await deps.automation.assertMayRun(deps.organizationId, 'trendHunter');

  // Recent topics are passed in so the hunter does not rediscover known stories.
  const existing = await prisma.topic.findMany({
    where: { organizationId: deps.organizationId, createdAt: { gte: new Date(Date.now() - 14 * 86_400_000) } },
    select: { id: true, title: true, summary: true },
    take: 300,
  });

  const agent = new TrendHunterAgent(agentContext(deps), deps.searchProviders);
  const discovered = await agent.run({
    maxTopics,
    existingTopics: existing.map((t) => ({ id: t.id, text: `${t.title} ${t.summary}` })),
  });

  const brand = await prisma.brand.findFirst({
    where: { organizationId: deps.organizationId, isDefault: true },
    select: { id: true },
  });

  let created = 0;
  for (const topic of discovered) {
    const row = await prisma.topic.create({
      data: {
        organizationId: deps.organizationId,
        brandId: brand?.id ?? null,
        title: topic.title,
        summary: topic.summary,
        category: topic.category,
        status: 'DISCOVERED',
        discoverySource: topic.discoverySource,
        discoveryUrl: topic.discoveryUrl ?? null,
        keywords: topic.keywords,
        entities: topic.entities,
        isBreakingNews: topic.isBreakingNews,
        contentHash: topic.contentHash,
        // Breaking news decays fast; evergreen stays useful for a fortnight.
        expiresAt: new Date(Date.now() + (topic.isBreakingNews ? 2 : 14) * 86_400_000),
      },
    });

    for (const source of topic.sources) {
      await prisma.source.create({
        data: {
          topicId: row.id,
          url: source.url,
          title: source.title,
          publisher: source.publisher ?? null,
          publishedAt: source.publishedAt ?? null,
          excerpt: source.snippet,
        },
      });
    }
    created++;
  }

  deps.logger.info({ created }, 'trend scan complete');
  return created;
}

/** Scores unscored topics and marks the strongest as selected. */
export async function runTopicScoring(deps: PipelineDeps, limit = 20): Promise<number> {
  await deps.automation.assertMayRun(deps.organizationId, 'topicScorer');

  const topics = await prisma.topic.findMany({
    where: { organizationId: deps.organizationId, status: 'DISCOVERED' },
    orderBy: { createdAt: 'desc' },
    take: limit,
  });
  if (topics.length === 0) return 0;

  const brand = await prisma.brand.findFirst({
    where: { organizationId: deps.organizationId, isDefault: true },
    select: { scoringWeights: true },
  });

  const agent = new TopicScorerAgent(agentContext(deps));
  const scored = await agent.run({
    topics: topics.map((t) => ({
      id: t.id,
      title: t.title,
      summary: t.summary,
      category: t.category,
      isBreakingNews: t.isBreakingNews,
      discoveredAt: t.createdAt,
    })),
    ...(brand?.scoringWeights ? { weights: brand.scoringWeights as Record<string, number> } : {}),
  });

  for (const result of scored) {
    await prisma.topic.update({
      where: { id: result.id },
      data: {
        dimensionScores: result.dimensionScores,
        compositeScore: result.compositeScore,
        // A weak topic is not worth researching; researching costs real money.
        status: result.compositeScore >= 60 ? 'SELECTED' : 'SCORED',
        scoredAt: new Date(),
      },
    });
  }

  return scored.length;
}

/** Researches one selected topic and fact-checks its claims. */
export async function runResearch(deps: PipelineDeps, topicId: string): Promise<{ claims: number; verified: number }> {
  await deps.automation.assertMayRun(deps.organizationId, 'researcher');

  const topic = await prisma.topic.findFirst({
    where: { id: topicId, organizationId: deps.organizationId },
    include: { sources: true },
  });
  if (!topic) throw new Error(`Topic not found: ${topicId}`);

  await prisma.topic.update({ where: { id: topicId }, data: { status: 'RESEARCHING' } });

  const ctx = agentContext(deps);
  const researcher = new ResearcherAgent(ctx, deps.searchProviders);
  const result = await researcher.run({
    topicId,
    title: topic.title,
    summary: topic.summary,
    keywords: topic.keywords,
    knownSources: topic.sources.map((s) => ({
      title: s.title,
      url: s.url,
      snippet: s.excerpt ?? '',
      ...(s.publisher ? { publisher: s.publisher } : {}),
      ...(s.publishedAt ? { publishedAt: s.publishedAt } : {}),
    })),
  });

  // Persist sources first so each claim can reference the source it came from.
  const sourceIds = new Map<string, string>();
  for (const source of result.sources) {
    const row = await prisma.source.upsert({
      where: { id: `${topicId}:${source.url}`.slice(0, 30) },
      create: {
        topicId,
        url: source.url,
        title: source.title,
        publisher: source.publisher ?? null,
        publishedAt: source.publishedAt ?? null,
        excerpt: source.excerpt,
        fullText: source.fullText ?? null,
        credibility: source.credibility,
      },
      update: {},
    }).catch(async () =>
      prisma.source.create({
        data: {
          topicId,
          url: source.url,
          title: source.title,
          publisher: source.publisher ?? null,
          publishedAt: source.publishedAt ?? null,
          excerpt: source.excerpt,
          fullText: source.fullText ?? null,
          credibility: source.credibility,
        },
      }),
    );
    sourceIds.set(source.url, row.id);
  }

  const claimRows = [];
  for (const claim of result.research.claims) {
    claimRows.push(
      await prisma.claim.create({
        data: {
          topicId,
          text: claim.text,
          claimType: claim.claimType,
          confidence: claim.confidence,
          verification: 'UNVERIFIED',
        },
      }),
    );
  }

  await prisma.researchReport.create({
    data: {
      topicId,
      summary: result.research.summary,
      keyFindings: result.research.keyFindings,
      angles: result.research.angles,
      people: result.research.people,
      companies: result.research.companies,
      contradictions: result.research.contradictions,
      sourceCount: result.sources.length,
      claimCount: claimRows.length,
    },
  });

  // Fact check, then write the verdicts back onto the claim rows.
  const checker = new FactCheckerAgent(ctx);
  const check = await checker.run({
    topicId,
    claims: claimRows.map((c, i) => ({
      id: c.id,
      text: c.text,
      claimType: c.claimType,
      supportingExcerpt: result.research.claims[i]?.supportingExcerpt ?? '',
    })),
    sources: result.sources,
  });

  for (const checked of check.claims) {
    await prisma.claim.update({
      where: { id: checked.id },
      data: {
        verification: checked.verification,
        confidence: checked.confidence,
        corroborationCount: checked.corroborationCount,
        verifierNotes: checked.notes,
        verifiedAt: new Date(),
      },
    });
  }

  await prisma.researchReport.updateMany({
    where: { topicId },
    data: { verifiedCount: check.verifiedCount },
  });
  await prisma.topic.update({
    where: { id: topicId },
    data: { status: check.requiresHumanReview ? 'REJECTED' : 'RESEARCHED' },
  });

  if (check.requiresHumanReview) {
    deps.logger.warn({ topicId, reason: check.reviewReason }, 'topic rejected after fact check');
  }

  return { claims: check.claims.length, verified: check.verifiedCount };
}
