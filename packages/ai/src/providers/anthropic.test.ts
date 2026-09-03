import { afterEach, describe, expect, it } from 'vitest';
import nock from 'nock';
import { z } from 'zod';
import { AnthropicProvider } from './anthropic.js';
import { AiError, ProviderNotConfiguredError } from '@mmos/core';

const HOST = 'https://api.anthropic.com';
const provider = new AnthropicProvider({ apiKey: 'test-key', model: 'claude-sonnet-5' });

function reply(text: string, status = 200) {
  return nock(HOST)
    .post('/v1/messages')
    .reply(status, {
      content: [{ type: 'text', text }],
      model: 'claude-sonnet-5',
      stop_reason: 'end_turn',
      usage: { input_tokens: 1000, output_tokens: 500 },
    });
}

afterEach(() => nock.cleanAll());

describe('AnthropicProvider', () => {
  it('refuses to construct without an API key rather than degrading silently', () => {
    expect(() => new AnthropicProvider({})).toThrow(ProviderNotConfiguredError);
  });

  it('computes cost from reported token usage', async () => {
    reply('hello');
    const res = await provider.complete({ messages: [{ role: 'user', content: 'hi' }] });
    // 1000 in @ $3/M + 500 out @ $15/M
    expect(res.usage.costUsd).toBeCloseTo(0.003 + 0.0075, 6);
  });

  it('validates structured output against the schema', async () => {
    reply('{"title":"A headline","count":3}');
    const schema = z.object({ title: z.string(), count: z.number() });
    const { data } = await provider.completeStructured(
      { messages: [{ role: 'user', content: 'go' }] },
      schema,
      'Test',
    );
    expect(data).toEqual({ title: 'A headline', count: 3 });
  });

  it('rejects output that does not satisfy the schema instead of passing it through', async () => {
    reply('{"title":"A headline"}'); // missing `count`
    const schema = z.object({ title: z.string(), count: z.number() });
    await expect(
      provider.completeStructured({ messages: [{ role: 'user', content: 'go' }] }, schema, 'Test'),
    ).rejects.toThrow(/failed Test validation/);
  });

  it('treats a 400 as non-retryable so a bad request is not paid for repeatedly', async () => {
    nock(HOST).post('/v1/messages').reply(400, { error: { message: 'bad request' } });
    await expect(provider.complete({ messages: [{ role: 'user', content: 'hi' }] })).rejects.toBeInstanceOf(
      AiError,
    );
    // A single attempt: the interceptor is consumed exactly once.
    expect(nock.pendingMocks()).toEqual([]);
  });

  it('retries a 500 and succeeds on the second attempt', async () => {
    nock(HOST).post('/v1/messages').reply(500, {});
    reply('recovered');
    const res = await provider.complete({ messages: [{ role: 'user', content: 'hi' }] });
    expect(res.text).toBe('recovered');
  });
});
