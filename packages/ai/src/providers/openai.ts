/**
 * OpenAI LLM provider. Interchangeable with the Anthropic provider — the agents
 * cannot tell which one they are talking to.
 */
import { AiError, ProviderNotConfiguredError, withRetry } from '@mmos/core';
import type { z } from 'zod';
import type { LlmProvider, LlmRequest, LlmResponse, LlmUsage } from '../types.js';
import { completeStructuredWith } from '../structured.js';

const API_URL = 'https://api.openai.com/v1/chat/completions';

/** USD per million tokens. */
const PRICING: Record<string, { input: number; output: number }> = {
  'gpt-4o': { input: 2.5, output: 10 },
  'gpt-4o-mini': { input: 0.15, output: 0.6 },
};
const DEFAULT_PRICING = { input: 2.5, output: 10 };

interface OpenAiResponse {
  choices: Array<{ message: { content: string | null }; finish_reason?: string }>;
  model: string;
  usage?: { prompt_tokens: number; completion_tokens: number };
}

export class OpenAiProvider implements LlmProvider {
  readonly name = 'openai';
  readonly defaultModel: string;
  readonly #apiKey: string;
  readonly #baseUrl: string;

  constructor(config: { apiKey?: string; model?: string; baseUrl?: string }) {
    if (!config.apiKey) throw new ProviderNotConfiguredError('OpenAI LLM', ['OPENAI_API_KEY']);
    this.#apiKey = config.apiKey;
    this.defaultModel = config.model ?? 'gpt-4o';
    this.#baseUrl = config.baseUrl ?? API_URL;
  }

  estimateCost(inputTokens: number, outputTokens: number, model?: string): number {
    const p = PRICING[model ?? this.defaultModel] ?? DEFAULT_PRICING;
    return (inputTokens / 1e6) * p.input + (outputTokens / 1e6) * p.output;
  }

  async #call(request: LlmRequest, jsonMode: boolean): Promise<LlmResponse> {
    const model = request.model ?? this.defaultModel;
    const messages = [
      ...(request.system ? [{ role: 'system' as const, content: request.system }] : []),
      ...request.messages,
    ];

    const body = await withRetry(
      async () => {
        const res = await fetch(this.#baseUrl, {
          method: 'POST',
          headers: { 'content-type': 'application/json', authorization: `Bearer ${this.#apiKey}` },
          body: JSON.stringify({
            model,
            messages,
            max_tokens: request.maxTokens ?? 4000,
            temperature: request.temperature ?? 0.7,
            ...(jsonMode ? { response_format: { type: 'json_object' } } : {}),
          }),
        });
        if (!res.ok) {
          const text = await res.text();
          throw new AiError(`OpenAI returned HTTP ${res.status}: ${text.slice(0, 500)}`, {
            retryable: res.status === 429 || res.status >= 500,
            context: { status: res.status, model },
          });
        }
        return (await res.json()) as OpenAiResponse;
      },
      { maxAttempts: 3, baseDelayMs: 1000 },
    );

    const inputTokens = body.usage?.prompt_tokens ?? 0;
    const outputTokens = body.usage?.completion_tokens ?? 0;
    const finish = body.choices[0]?.finish_reason;

    return {
      text: body.choices[0]?.message.content ?? '',
      model: body.model,
      usage: { inputTokens, outputTokens, costUsd: this.estimateCost(inputTokens, outputTokens, body.model) },
      ...(finish ? { stopReason: finish } : {}),
    };
  }

  async complete(request: LlmRequest): Promise<LlmResponse> {
    return this.#call(request, false);
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
    ]
      .join('\n')
      .trim();

    return completeStructuredWith({
      providerName: 'OpenAI',
      complete: (req) => this.#call({ ...req, system }, true),
      request,
      schema,
      schemaName,
    });
  }
}
