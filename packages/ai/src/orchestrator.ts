/**
 * AI orchestrator.
 *
 * Every model call in the system goes through here. That single choke point is
 * what makes two guarantees possible:
 *  - Cost is metered and attributed. "What did this post cost to produce?" is
 *    answerable per topic and per content piece.
 *  - A budget ceiling is checked BEFORE dispatch, so an agent stuck in a retry
 *    loop cannot quietly spend a month's budget overnight.
 */
import { BudgetExceededError, type Logger } from '@mmos/core';
import type { z } from 'zod';
import type { LlmProvider, LlmRequest, LlmUsage } from './types.js';

export interface CostSink {
  record(entry: {
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
  }): Promise<void>;

  /** Spend in the rolling window, used by the budget gate. */
  spentToday(): Promise<number>;
  spentThisMonth(): Promise<number>;
}

/** No-op sink for tests and for running an agent outside a database context. */
export class NullCostSink implements CostSink {
  readonly entries: Array<{ costUsd: number; operation: string }> = [];
  async record(entry: { costUsd: number; operation: string }): Promise<void> {
    this.entries.push(entry);
  }
  async spentToday(): Promise<number> {
    return this.entries.reduce((sum, e) => sum + e.costUsd, 0);
  }
  async spentThisMonth(): Promise<number> {
    return this.spentToday();
  }
}

export interface OrchestratorOptions {
  llm: LlmProvider;
  costSink: CostSink;
  logger: Logger;
  dailyLimitUsd: number;
  monthlyLimitUsd: number;
}

export interface CallAttribution {
  operation: string;
  topicId?: string;
  contentPieceId?: string;
}

export class AiOrchestrator {
  readonly #llm: LlmProvider;
  readonly #costs: CostSink;
  readonly #log: Logger;
  readonly #dailyLimit: number;
  readonly #monthlyLimit: number;

  constructor(opts: OrchestratorOptions) {
    this.#llm = opts.llm;
    this.#costs = opts.costSink;
    this.#log = opts.logger;
    this.#dailyLimit = opts.dailyLimitUsd;
    this.#monthlyLimit = opts.monthlyLimitUsd;
  }

  get providerName(): string {
    return this.#llm.name;
  }

  /**
   * Checked before dispatch, not after. Checking afterwards would mean the
   * money is already spent by the time the limit is noticed.
   */
  async assertWithinBudget(): Promise<void> {
    const [today, month] = await Promise.all([this.#costs.spentToday(), this.#costs.spentThisMonth()]);
    if (today >= this.#dailyLimit) throw new BudgetExceededError('daily', today, this.#dailyLimit);
    if (month >= this.#monthlyLimit) throw new BudgetExceededError('monthly', month, this.#monthlyLimit);
  }

  async complete(request: LlmRequest, attribution: CallAttribution): Promise<string> {
    await this.assertWithinBudget();
    const started = Date.now();
    const response = await this.#llm.complete(request);
    await this.#meter(response.usage, response.model, attribution);
    this.#log.debug(
      {
        operation: attribution.operation,
        model: response.model,
        costUsd: response.usage.costUsd,
        durationMs: Date.now() - started,
      },
      'llm call complete',
    );
    return response.text;
  }

  async completeStructured<T>(
    request: LlmRequest,
    schema: z.ZodType<T>,
    schemaName: string,
    attribution: CallAttribution,
  ): Promise<T> {
    await this.assertWithinBudget();
    const started = Date.now();
    const result = await this.#llm.completeStructured(request, schema, schemaName);
    await this.#meter(result.usage, result.model, attribution);
    this.#log.debug(
      {
        operation: attribution.operation,
        schema: schemaName,
        model: result.model,
        costUsd: result.usage.costUsd,
        durationMs: Date.now() - started,
      },
      'structured llm call complete',
    );
    return result.data;
  }

  async #meter(usage: LlmUsage, model: string, attribution: CallAttribution): Promise<void> {
    await this.#costs.record({
      service: 'llm',
      provider: this.#llm.name,
      model,
      operation: attribution.operation,
      inputTokens: usage.inputTokens,
      outputTokens: usage.outputTokens,
      costUsd: usage.costUsd,
      ...(attribution.topicId ? { topicId: attribution.topicId } : {}),
      ...(attribution.contentPieceId ? { contentPieceId: attribution.contentPieceId } : {}),
    });
  }

  async budgetStatus(): Promise<{
    dailySpent: number;
    dailyLimit: number;
    monthlySpent: number;
    monthlyLimit: number;
    dailyRemaining: number;
    monthlyRemaining: number;
    halted: boolean;
  }> {
    const [dailySpent, monthlySpent] = await Promise.all([
      this.#costs.spentToday(),
      this.#costs.spentThisMonth(),
    ]);
    return {
      dailySpent,
      dailyLimit: this.#dailyLimit,
      monthlySpent,
      monthlyLimit: this.#monthlyLimit,
      dailyRemaining: Math.max(0, this.#dailyLimit - dailySpent),
      monthlyRemaining: Math.max(0, this.#monthlyLimit - monthlySpent),
      halted: dailySpent >= this.#dailyLimit || monthlySpent >= this.#monthlyLimit,
    };
  }
}
