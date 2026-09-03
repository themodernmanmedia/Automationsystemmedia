/**
 * Retry with exponential backoff and full jitter.
 *
 * Jitter matters here specifically: when a platform rate-limits us, every queued
 * publish job fails at nearly the same instant. Without jitter they would all
 * retry in lockstep and re-trigger the same limit. Full jitter spreads them out.
 */
import { isRetryable, retryAfterOf } from './errors.js';

export interface RetryOptions {
  maxAttempts?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  /** Defaults to the error taxonomy's `retryable` flag. */
  shouldRetry?: (err: unknown, attempt: number) => boolean;
  onRetry?: (err: unknown, attempt: number, delayMs: number) => void;
  signal?: AbortSignal;
}

export function backoffDelay(attempt: number, baseMs = 500, maxMs = 60_000): number {
  const exponential = Math.min(maxMs, baseMs * 2 ** (attempt - 1));
  return Math.floor(Math.random() * exponential); // full jitter
}

export async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new Error('Aborted'));
    };
    if (signal?.aborted) return onAbort();
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

export async function withRetry<T>(fn: (attempt: number) => Promise<T>, options: RetryOptions = {}): Promise<T> {
  const {
    maxAttempts = 3,
    baseDelayMs = 500,
    maxDelayMs = 60_000,
    shouldRetry = isRetryable,
    onRetry,
    signal,
  } = options;

  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn(attempt);
    } catch (err) {
      lastError = err;
      if (attempt >= maxAttempts || !shouldRetry(err, attempt)) throw err;
      // Honor a server-supplied Retry-After over our own guess.
      const delay = retryAfterOf(err) ?? backoffDelay(attempt, baseDelayMs, maxDelayMs);
      onRetry?.(err, attempt, delay);
      await sleep(delay, signal);
    }
  }
  throw lastError;
}
