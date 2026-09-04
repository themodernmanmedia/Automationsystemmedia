/**
 * Structured output with self-correction.
 *
 * Shared by every LLM provider, because the failure mode and the fix are the
 * same regardless of vendor.
 *
 * Why self-correction matters here: a schema failure is thrown after the HTTP
 * call has already succeeded, so the provider's own network retry does not
 * cover it. Without this, the error propagates out of the agent, fails the
 * whole job, and BullMQ re-runs it from the top — re-paying for research and
 * every other call the agent had already made. Feeding the validation errors
 * back and asking for a correction costs one short completion instead.
 *
 * One correction attempt, not many: if a model cannot satisfy the schema when
 * shown exactly what was wrong, further identical requests rarely help and the
 * job retry is the right escalation.
 */
import { AiError } from '@mmos/core';
import type { z } from 'zod';
import type { LlmRequest, LlmResponse, LlmUsage } from './types.js';
import { extractJson } from './json.js';

export interface StructuredResult<T> {
  data: T;
  usage: LlmUsage;
  model: string;
}

/** Renders Zod issues as instructions a model can act on. */
function describeIssues(error: z.ZodError): string {
  return error.issues
    .map((issue) => {
      const path = issue.path.join('.') || '(root)';
      return `- ${path}: ${issue.message}`;
    })
    .join('\n');
}

export async function completeStructuredWith<T>(
  options: {
    providerName: string;
    /** The provider's plain completion, already configured for JSON output. */
    complete: (request: LlmRequest) => Promise<LlmResponse>;
    request: LlmRequest;
    schema: z.ZodType<T, z.ZodTypeDef, unknown>;
    schemaName: string;
  },
): Promise<StructuredResult<T>> {
  const { providerName, complete, request, schema, schemaName } = options;

  const attempt = async (
    messages: LlmRequest['messages'],
  ): Promise<{ ok: true; data: T; response: LlmResponse } | { ok: false; response: LlmResponse; reason: string }> => {
    const response = await complete({ ...request, messages });

    let parsed: unknown;
    try {
      parsed = extractJson(response.text);
    } catch (err) {
      return { ok: false, response, reason: `The response was not valid JSON: ${(err as Error).message}` };
    }

    const result = schema.safeParse(parsed);
    if (!result.success) {
      return { ok: false, response, reason: describeIssues(result.error) };
    }
    return { ok: true, data: result.data, response };
  };

  const first = await attempt(request.messages);
  if (first.ok) {
    return { data: first.data, usage: first.response.usage, model: first.response.model };
  }

  // Show the model its own output and exactly what was wrong with it.
  const correction = await attempt([
    ...request.messages,
    { role: 'assistant', content: first.response.text.slice(0, 8000) },
    {
      role: 'user',
      content:
        `That response did not satisfy the "${schemaName}" schema:\n\n${first.reason}\n\n` +
        `Return the corrected JSON object only. Fix exactly these problems and change nothing else.`,
    },
  ]);

  // Both attempts are billed, so report the combined cost rather than the
  // second alone — otherwise the cost meter understates what was spent.
  const combinedUsage = (r: LlmResponse): LlmUsage => ({
    inputTokens: first.response.usage.inputTokens + r.usage.inputTokens,
    outputTokens: first.response.usage.outputTokens + r.usage.outputTokens,
    costUsd: first.response.usage.costUsd + r.usage.costUsd,
  });

  if (correction.ok) {
    return {
      data: correction.data,
      usage: combinedUsage(correction.response),
      model: correction.response.model,
    };
  }

  throw new AiError(
    `${providerName} output failed ${schemaName} validation after a correction attempt: ${correction.reason}`,
    {
      // Still retryable: the job retry is the right next escalation.
      retryable: true,
      context: {
        firstFailure: first.reason,
        secondFailure: correction.reason,
        preview: correction.response.text.slice(0, 500),
      },
    },
  );
}
