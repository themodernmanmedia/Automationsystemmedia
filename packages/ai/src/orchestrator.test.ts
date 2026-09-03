import { describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import { AiOrchestrator, NullCostSink, type CostSink } from './orchestrator.js';
import { BudgetExceededError, createLogger } from '@mmos/core';
import type { LlmProvider } from './types.js';

const logger = createLogger({ level: 'silent' });

function fakeLlm(overrides: Partial<LlmProvider> = {}): LlmProvider {
  return {
    name: 'fake',
    defaultModel: 'fake-1',
    estimateCost: () => 0.01,
    complete: vi.fn(async () => ({
      text: 'hello',
      model: 'fake-1',
      usage: { inputTokens: 100, outputTokens: 50, costUsd: 0.01 },
    })),
    completeStructured: vi.fn(async () => ({
      data: { ok: true } as never,
      usage: { inputTokens: 100, outputTokens: 50, costUsd: 0.02 },
      model: 'fake-1',
    })),
    ...overrides,
  };
}

/** Sink with a fixed reported spend, to drive the budget gate. */
function sinkAt(dailySpend: number, monthlySpend = dailySpend): CostSink {
  return {
    record: vi.fn(async () => {}),
    spentToday: async () => dailySpend,
    spentThisMonth: async () => monthlySpend,
  };
}

describe('AiOrchestrator', () => {
  it('meters cost and attributes it to the content piece', async () => {
    const sink = new NullCostSink();
    const recordSpy = vi.spyOn(sink, 'record');
    const orch = new AiOrchestrator({
      llm: fakeLlm(),
      costSink: sink,
      logger,
      dailyLimitUsd: 25,
      monthlyLimitUsd: 500,
    });

    await orch.complete({ messages: [{ role: 'user', content: 'hi' }] }, {
      operation: 'hook_generation',
      contentPieceId: 'cp-1',
      topicId: 't-1',
    });

    expect(recordSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        service: 'llm',
        operation: 'hook_generation',
        contentPieceId: 'cp-1',
        topicId: 't-1',
        costUsd: 0.01,
        inputTokens: 100,
      }),
    );
  });

  it('refuses to dispatch once the daily limit is reached', async () => {
    const llm = fakeLlm();
    const orch = new AiOrchestrator({
      llm,
      costSink: sinkAt(25.5),
      logger,
      dailyLimitUsd: 25,
      monthlyLimitUsd: 500,
    });

    await expect(
      orch.complete({ messages: [{ role: 'user', content: 'hi' }] }, { operation: 'x' }),
    ).rejects.toBeInstanceOf(BudgetExceededError);

    // The critical assertion: the money is never spent. The gate runs BEFORE
    // dispatch, so the provider is never called.
    expect(llm.complete).not.toHaveBeenCalled();
  });

  it('refuses on the monthly limit even when the day is cheap', async () => {
    const llm = fakeLlm();
    const orch = new AiOrchestrator({
      llm,
      costSink: sinkAt(1, 501),
      logger,
      dailyLimitUsd: 25,
      monthlyLimitUsd: 500,
    });

    await expect(
      orch.complete({ messages: [{ role: 'user', content: 'hi' }] }, { operation: 'x' }),
    ).rejects.toThrow(/monthly AI budget exceeded/);
    expect(llm.complete).not.toHaveBeenCalled();
  });

  it('reports a budget status the dashboard can render', async () => {
    const orch = new AiOrchestrator({
      llm: fakeLlm(),
      costSink: sinkAt(10, 120),
      logger,
      dailyLimitUsd: 25,
      monthlyLimitUsd: 500,
    });
    const status = await orch.budgetStatus();
    expect(status).toMatchObject({
      dailySpent: 10,
      dailyRemaining: 15,
      monthlySpent: 120,
      monthlyRemaining: 380,
      halted: false,
    });
  });

  it('passes structured output through the schema', async () => {
    const schema = z.object({ ok: z.boolean() });
    const orch = new AiOrchestrator({
      llm: fakeLlm(),
      costSink: new NullCostSink(),
      logger,
      dailyLimitUsd: 25,
      monthlyLimitUsd: 500,
    });
    const result = await orch.completeStructured(
      { messages: [{ role: 'user', content: 'hi' }] },
      schema,
      'Test',
      { operation: 'test' },
    );
    expect(result).toEqual({ ok: true });
  });
});
