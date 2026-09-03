/**
 * Anthropic LLM provider.
 *
 * Calls the Messages API directly over fetch rather than pulling in the SDK:
 * the surface used here is small, and it keeps the provider boundary free of a
 * vendor dependency that agents might otherwise start leaning on.
 */
import { AiError, ProviderNotConfiguredError, withRetry } from '@mmos/core';
import type { z } from 'zod';
import type { LlmProvider, LlmRequest, LlmResponse, LlmUsage } from '../types.js';
import { extractJson } from '../json.js';

const API_URL = 'https://api.anthropic.com/v1/messages';
const API_VERSION = '2023-06-01';

/** USD per million tokens. Update alongside Anthropic's published pricing. */
const PRICING: Record<string, { input: number; output: number }> = {
  'claude-opus-5': { input: 5, output: 25 },
  'claude-sonnet-5': { input: 3, output: 15 },
  'claude-haiku-4-5-20251001': { input: 1, output: 5 },
};
const DEFAULT_PRICING = { input: 3, output: 15 };

interface AnthropicResponse {
  content: Array<{ type: string; text?: string }>;
  model: string;
  stop_reason?: string;
  usage: { input_tokens: number; output_tokens: number };
}

export class AnthropicProvider implements LlmProvider {
  readonly name = 'anthropic';
  readonly defaultModel: string;
  readonly #apiKey: string;
  readonly #baseUrl: string;

  constructor(config: { apiKey?: string; model?: string; baseUrl?: string }) {
    if (!config.apiKey) throw new ProviderNotConfiguredError('Anthropic LLM', ['ANTHROPIC_API_KEY']);
    this.#apiKey = config.apiKey;
    this.defaultModel = config.model ?? 'claude-sonnet-5';
    this.#baseUrl = config.baseUrl ?? API_URL;
  }

  estimateCost(inputTokens: number, outputTokens: number, model?: string): number {
    const p = PRICING[model ?? this.defaultModel] ?? DEFAULT_PRICING;
    return (inputTokens / 1e6) * p.input + (outputTokens / 1e6) * p.output;
  }

  async complete(request: LlmRequest): Promise<LlmResponse> {
    const model = request.model ?? this.defaultModel;

    const body = await withRetry(
      async () => {
        const res = await fetch(this.#baseUrl, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            'x-api-key': this.#apiKey,
            'anthropic-version': API_VERSION,
          },
          body: JSON.stringify({
            model,
            max_tokens: request.maxTokens ?? 4000,
            temperature: request.temperature ?? 0.7,
            ...(request.system ? { system: request.system } : {}),
            messages: request.messages,
          }),
        });

        if (!res.ok) {
          const text = await res.text();
          throw new AiError(`Anthropic returned HTTP ${res.status}: ${text.slice(0, 500)}`, {
            // 429 and 5xx are transient; a 400 means our request is wrong and
            // retrying it only wastes money.
            retryable: res.status === 429 || res.status >= 500,
            context: { status: res.status, model },
          });
        }
        return (await res.json()) as AnthropicResponse;
      },
      { maxAttempts: 3, baseDelayMs: 1000 },
    );

    const text = body.content
      .filter((c) => c.type === 'text')
      .map((c) => c.text ?? '')
      .join('');

    const usage: LlmUsage = {
      inputTokens: body.usage.input_tokens,
      outputTokens: body.usage.output_tokens,
      costUsd: this.estimateCost(body.usage.input_tokens, body.usage.output_tokens, body.model),
    };

    return { text, model: body.model, usage, ...(body.stop_reason ? { stopReason: body.stop_reason } : {}) };
  }

  async completeStructured<T>(
    request: LlmRequest,
    schema: z.ZodType<T, z.ZodTypeDef, unknown>,
    schemaName: string,
  ): Promise<{ data: T; usage: LlmUsage; model: string }> {
    const system = [
      request.system ?? '',
      '',
      `Respond with a single JSON object matching the "${schemaName}" schema.`,
      'Output raw JSON only: no prose, no explanation, no markdown code fences.',
    ]
      .join('\n')
      .trim();

    const response = await this.complete({ ...request, system });

    let parsed: unknown;
    try {
      parsed = extractJson(response.text);
    } catch (err) {
      throw new AiError(`Anthropic did not return parseable JSON for ${schemaName}: ${(err as Error).message}`, {
        retryable: true,
        context: { preview: response.text.slice(0, 500) },
      });
    }

    const result = schema.safeParse(parsed);
    if (!result.success) {
      // Retryable on purpose: a schema miss is usually a one-off sampling
      // artifact, and the caller's retry gives a second sample.
      throw new AiError(
        `Anthropic output failed ${schemaName} validation: ${result.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ')}`,
        { retryable: true, context: { preview: response.text.slice(0, 500) } },
      );
    }

    return { data: result.data, usage: response.usage, model: response.model };
  }
}
