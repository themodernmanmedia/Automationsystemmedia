/**
 * Shared HTTP layer for platform calls.
 *
 * Its real job is error classification: turning a platform's arbitrary error
 * shape into the typed taxonomy so the retry policy can act without
 * string-matching. Getting this wrong is expensive — retrying a revoked token
 * burns rate limit and never succeeds, while failing to retry a 503 drops a post.
 */
import { PlatformApiError, PlatformAuthError, RateLimitError } from '@mmos/core';

export interface HttpRequest {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  url: string;
  headers?: Record<string, string>;
  body?: unknown;
  /** Sends the body as form-encoded rather than JSON (Meta expects this). */
  form?: Record<string, string>;
  timeoutMs?: number;
}

export interface HttpResponse<T = unknown> {
  status: number;
  headers: Record<string, string>;
  body: T;
  durationMs: number;
}

/** Meta returns errors under `error`; TikTok under `error.code` with a string code. */
interface MetaErrorBody {
  error?: { message?: string; type?: string; code?: number; error_subcode?: number; fbtrace_id?: string };
}
interface TikTokErrorBody {
  error?: { code?: string; message?: string; log_id?: string };
}

export async function request<T = unknown>(req: HttpRequest, platform: string): Promise<HttpResponse<T>> {
  const start = Date.now();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), req.timeoutMs ?? 60_000);

  let init: RequestInit;
  const headers: Record<string, string> = { Accept: 'application/json', ...req.headers };

  if (req.form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
    init = { method: req.method, headers, body: new URLSearchParams(req.form).toString() };
  } else if (req.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init = { method: req.method, headers, body: JSON.stringify(req.body) };
  } else {
    init = { method: req.method, headers };
  }
  init.signal = controller.signal;

  let res: Response;
  try {
    res = await fetch(req.url, init);
  } catch (err) {
    clearTimeout(timeout);
    // Network faults and timeouts are transient by nature — always retryable.
    throw new PlatformApiError(platform, `Network error calling ${platform}: ${(err as Error).message}`, {
      retryable: true,
      cause: err,
      context: { url: redactUrl(req.url) },
    });
  }
  clearTimeout(timeout);

  const durationMs = Date.now() - start;
  const text = await res.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : {};
  } catch {
    parsed = { raw: text };
  }

  if (!res.ok) throw classifyError(platform, res, parsed, req.url);

  return {
    status: res.status,
    headers: Object.fromEntries(res.headers.entries()),
    body: parsed as T,
    durationMs,
  };
}

function classifyError(platform: string, res: Response, body: unknown, url: string): Error {
  const meta = (body as MetaErrorBody).error;
  const tiktok = (body as TikTokErrorBody).error;
  const message =
    meta?.message ?? tiktok?.message ?? `${platform} returned HTTP ${res.status}`;
  const context = { url: redactUrl(url), status: res.status, body };

  // 401/403, plus Meta's OAuthException family, mean the token is bad. Retrying
  // cannot help and only consumes quota, so these are explicitly non-retryable.
  if (res.status === 401 || res.status === 403 || meta?.type === 'OAuthException') {
    return new PlatformAuthError(platform, message, { context });
  }

  if (res.status === 429 || meta?.code === 4 || meta?.code === 17 || meta?.code === 32) {
    const retryAfterHeader = res.headers.get('retry-after');
    const retryAfterMs = retryAfterHeader ? Number(retryAfterHeader) * 1000 : 60_000;
    return new RateLimitError(platform, message, retryAfterMs, context);
  }

  // 5xx is the platform's problem and usually transient; 4xx is ours and is not.
  return new PlatformApiError(platform, message, {
    retryable: res.status >= 500,
    platformCode: meta?.code ?? tiktok?.code ?? res.status,
    context,
  });
}

/** Strip credentials from URLs before they reach a log or an error context. */
export function redactUrl(url: string): string {
  try {
    const u = new URL(url);
    for (const key of ['access_token', 'client_secret', 'code', 'refresh_token']) {
      if (u.searchParams.has(key)) u.searchParams.set(key, '[REDACTED]');
    }
    return u.toString();
  } catch {
    return url;
  }
}

export function buildUrl(base: string, path: string, params: Record<string, string | undefined> = {}): string {
  const url = new URL(path.replace(/^\//, ''), base.endsWith('/') ? base : `${base}/`);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') url.searchParams.set(k, v);
  }
  return url.toString();
}
