/**
 * Database-backed cost meter.
 *
 * Implements the CostSink the AI orchestrator depends on, so cost is recorded
 * on the same code path as the call that incurs it — there is no way to make a
 * model call that escapes the meter.
 */
import { prisma } from '@mmos/db';
import type { CostSink } from '@mmos/ai';

export class DbCostSink implements CostSink {
  constructor(private readonly organizationId: string) {}

  async record(entry: {
    service: string;
    provider: string;
    model?: string;
    operation: string;
    inputTokens?: number;
    outputTokens?: number;
    units?: number;
    costUsd: number;
    topicId?: string;
    contentPieceId?: string;
  }): Promise<void> {
    await prisma.costEntry.create({
      data: {
        organizationId: this.organizationId,
        service: entry.service,
        provider: entry.provider,
        model: entry.model ?? null,
        operation: entry.operation,
        inputTokens: entry.inputTokens ?? null,
        outputTokens: entry.outputTokens ?? null,
        units: entry.units ?? null,
        costUsd: entry.costUsd,
        topicId: entry.topicId ?? null,
        contentPieceId: entry.contentPieceId ?? null,
      },
    });
  }

  async spentToday(): Promise<number> {
    return this.#sumSince(startOfUtcDay());
  }

  async spentThisMonth(): Promise<number> {
    return this.#sumSince(startOfUtcMonth());
  }

  async #sumSince(since: Date): Promise<number> {
    const result = await prisma.costEntry.aggregate({
      where: { organizationId: this.organizationId, createdAt: { gte: since } },
      _sum: { costUsd: true },
    });
    return result._sum.costUsd ?? 0;
  }

  /** Cost breakdown for the dashboard. */
  async breakdown(since: Date): Promise<Array<{ service: string; costUsd: number; calls: number }>> {
    const rows = await prisma.costEntry.groupBy({
      by: ['service'],
      where: { organizationId: this.organizationId, createdAt: { gte: since } },
      _sum: { costUsd: true },
      _count: { _all: true },
    });
    return rows
      .map((r) => ({ service: r.service, costUsd: r._sum.costUsd ?? 0, calls: r._count._all }))
      .sort((a, b) => b.costUsd - a.costUsd);
  }

  /** "What did this post cost to make?" — the traceability the brief asks for. */
  async costOfContentPiece(contentPieceId: string): Promise<number> {
    const result = await prisma.costEntry.aggregate({
      where: { contentPieceId },
      _sum: { costUsd: true },
    });
    return result._sum.costUsd ?? 0;
  }
}

function startOfUtcDay(): Date {
  const d = new Date();
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
}

function startOfUtcMonth(): Date {
  const d = new Date();
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1));
}
