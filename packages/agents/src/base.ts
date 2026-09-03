/**
 * Agent base.
 *
 * Real agents rather than one giant prompt, per the brief. Each agent has a
 * narrow contract, its own prompt, its own output schema, and its own run
 * record. The base class exists so that every agent is uniformly observable:
 * a run is always timed, always logged, and always attributable, without each
 * agent remembering to do it.
 */
import type { Logger } from '@mmos/core';
import { AppError } from '@mmos/core';
import type { AiOrchestrator } from '@mmos/ai';

export interface AgentRunRecord {
  agentName: string;
  status: 'SUCCESS' | 'FAILED';
  itemsProcessed: number;
  itemsProduced: number;
  durationMs: number;
  error?: { code: string; message: string; retryable: boolean };
}

/** Persistence for run records. A no-op implementation keeps agents usable in tests. */
export interface AgentRunSink {
  record(run: AgentRunRecord & { inputSummary?: unknown; outputSummary?: unknown }): Promise<void>;
}

export class NullRunSink implements AgentRunSink {
  readonly runs: AgentRunRecord[] = [];
  async record(run: AgentRunRecord): Promise<void> {
    this.runs.push(run);
  }
}

export interface AgentContext {
  organizationId: string;
  orchestrator: AiOrchestrator;
  logger: Logger;
  runSink: AgentRunSink;
}

export interface AgentResult<T> {
  output: T;
  itemsProcessed: number;
  itemsProduced: number;
}

export abstract class Agent<TInput, TOutput> {
  abstract readonly name: string;

  protected constructor(protected readonly ctx: AgentContext) {}

  protected abstract execute(input: TInput): Promise<AgentResult<TOutput>>;

  /**
   * Wraps execute() with timing, structured logging, and a persisted run
   * record for both success and failure. Failures are recorded and rethrown —
   * the caller decides whether to retry, and the record survives either way.
   */
  async run(input: TInput): Promise<TOutput> {
    const started = Date.now();
    const log = this.ctx.logger.child({ agent: this.name, organizationId: this.ctx.organizationId });
    log.info('agent run starting');

    try {
      const result = await this.execute(input);
      const durationMs = Date.now() - started;
      await this.ctx.runSink.record({
        agentName: this.name,
        status: 'SUCCESS',
        itemsProcessed: result.itemsProcessed,
        itemsProduced: result.itemsProduced,
        durationMs,
        outputSummary: summarize(result.output),
      });
      log.info(
        { durationMs, produced: result.itemsProduced, processed: result.itemsProcessed },
        'agent run complete',
      );
      return result.output;
    } catch (err) {
      const durationMs = Date.now() - started;
      const appErr = err instanceof AppError ? err : null;
      await this.ctx.runSink.record({
        agentName: this.name,
        status: 'FAILED',
        itemsProcessed: 0,
        itemsProduced: 0,
        durationMs,
        error: {
          code: appErr?.code ?? 'INTERNAL',
          message: (err as Error).message,
          retryable: appErr?.retryable ?? false,
        },
      });
      log.error({ err, durationMs }, 'agent run failed');
      throw err;
    }
  }
}

/** Keeps run records small — a full carousel payload in every row is noise. */
function summarize(output: unknown): unknown {
  if (Array.isArray(output)) return { count: output.length };
  if (output && typeof output === 'object') {
    const keys = Object.keys(output as Record<string, unknown>);
    return { keys: keys.slice(0, 12) };
  }
  return { value: typeof output };
}
