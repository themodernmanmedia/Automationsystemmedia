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
    // Two replies: the provider now shows the model its error and asks for a
    // correction before giving up. Both are wrong here.
    reply('{"title":"A headline"}'); // missing `count`
    reply('{"title":"Still wrong"}');
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

describe('self-correction on schema failure', () => {
  const schema = z.object({ title: z.string(), count: z.number() });

  function replyOnce(text: string, tokens = { input: 1000, output: 500 }) {
    return nock(HOST)
      .post('/v1/messages')
      .reply(200, {
        content: [{ type: 'text', text }],
        model: 'claude-sonnet-5',
        stop_reason: 'end_turn',
        usage: { input_tokens: tokens.input, output_tokens: tokens.output },
      });
  }

  it('recovers by showing the model exactly what was wrong', async () => {
    let correctionPrompt = '';
    // First response is missing `count`.
    replyOnce('{"title":"A headline"}');
    // Second call carries the correction; capture what we sent.
    nock(HOST)
      .post('/v1/messages', (body) => {
        correctionPrompt = JSON.stringify(body);
        return true;
      })
      .reply(200, {
        content: [{ type: 'text', text: '{"title":"A headline","count":3}' }],
        model: 'claude-sonnet-5',
        stop_reason: 'end_turn',
        usage: { input_tokens: 1200, output_tokens: 300 },
      });

    const { data, usage } = await provider.completeStructured(
      { messages: [{ role: 'user', content: 'go' }] },
      schema,
      'Test',
    );

    expect(data).toEqual({ title: 'A headline', count: 3 });
    // The model is told the field name and the problem, not just "invalid".
    expect(correctionPrompt).toContain('count');
    expect(correctionPrompt).toContain('Test');
    // Both attempts were billed, so both must be reported to the cost meter.
    expect(usage.inputTokens).toBe(2200);
    expect(usage.outputTokens).toBe(800);
  });

  it('recovers from unparseable JSON, not just schema misses', async () => {
    replyOnce('I cannot produce that.');
    replyOnce('{"title":"Recovered","count":1}');

    const { data } = await provider.completeStructured(
      { messages: [{ role: 'user', content: 'go' }] },
      schema,
      'Test',
    );
    expect(data).toEqual({ title: 'Recovered', count: 1 });
  });

  it('gives up after one correction rather than looping', async () => {
    replyOnce('{"title":"A"}');
    replyOnce('{"title":"B"}');

    await expect(
      provider.completeStructured({ messages: [{ role: 'user', content: 'go' }] }, schema, 'Test'),
    ).rejects.toThrow(/after a correction attempt/);

    // Exactly two calls: no third attempt was made.
    expect(nock.pendingMocks()).toEqual([]);
  });

  it('does not spend a second call when the first response is valid', async () => {
    replyOnce('{"title":"Fine","count":2}');

    const { usage } = await provider.completeStructured(
      { messages: [{ role: 'user', content: 'go' }] },
      schema,
      'Test',
    );
    expect(usage.inputTokens).toBe(1000);
    expect(nock.pendingMocks()).toEqual([]);
  });
});
