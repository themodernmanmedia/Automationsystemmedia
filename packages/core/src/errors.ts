/**
 * Typed error taxonomy.
 *
 * Every failure in the system is classified so that workers can decide, without
 * string-matching a message, whether a job should be retried, deferred, or sent
 * straight to the dead-letter queue. `retryable` and `retryAfterMs` are the two
 * fields the retry policy actually reads.
 */

export const ErrorCode = {
  API_ERROR: 'API_ERROR',
  AUTH_ERROR: 'AUTH_ERROR',
  RATE_LIMIT: 'RATE_LIMIT',
  MEDIA_ERROR: 'MEDIA_ERROR',
  AI_ERROR: 'AI_ERROR',
  DATABASE_ERROR: 'DATABASE_ERROR',
  PUBLISH_ERROR: 'PUBLISH_ERROR',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  CAPABILITY_NOT_SUPPORTED: 'CAPABILITY_NOT_SUPPORTED',
  PROVIDER_NOT_CONFIGURED: 'PROVIDER_NOT_CONFIGURED',
  BUDGET_EXCEEDED: 'BUDGET_EXCEEDED',
  POLICY_BLOCKED: 'POLICY_BLOCKED',
  NOT_FOUND: 'NOT_FOUND',
  FORBIDDEN: 'FORBIDDEN',
  CONFLICT: 'CONFLICT',
  INTERNAL: 'INTERNAL',
} as const;

export type ErrorCode = (typeof ErrorCode)[keyof typeof ErrorCode];

export interface AppErrorOptions {
  code?: ErrorCode;
  httpStatus?: number;
  retryable?: boolean;
  retryAfterMs?: number;
  context?: Record<string, unknown>;
  cause?: unknown;
}

export class AppError extends Error {
  readonly code: ErrorCode;
  readonly httpStatus: number;
  readonly retryable: boolean;
  readonly retryAfterMs?: number;
  readonly context: Record<string, unknown>;

  constructor(message: string, options: AppErrorOptions = {}) {
    super(message, options.cause !== undefined ? { cause: options.cause } : undefined);
    this.name = new.target.name;
    this.code = options.code ?? ErrorCode.INTERNAL;
    this.httpStatus = options.httpStatus ?? 500;
    this.retryable = options.retryable ?? false;
    if (options.retryAfterMs !== undefined) this.retryAfterMs = options.retryAfterMs;
    this.context = options.context ?? {};
    Error.captureStackTrace?.(this, new.target);
  }

  /** Safe for API responses — never leaks `context`, which may hold internals. */
  toPublicJSON(): { error: string; code: ErrorCode; message: string } {
    return { error: this.name, code: this.code, message: this.message };
  }
}

/** A platform API returned an error. Retryable only for 5xx / network faults. */
export class PlatformApiError extends AppError {
  readonly platform: string;
  readonly platformCode?: string | number;

  constructor(
    platform: string,
    message: string,
    options: AppErrorOptions & { platformCode?: string | number } = {},
  ) {
    super(message, { code: ErrorCode.API_ERROR, httpStatus: 502, ...options });
    this.platform = platform;
    if (options.platformCode !== undefined) this.platformCode = options.platformCode;
  }
}

/** Token missing, expired, revoked, or lacking a required scope. Never retryable —
 *  retrying an auth failure just burns rate limit. Needs human reconnect. */
export class PlatformAuthError extends AppError {
  readonly platform: string;
  constructor(platform: string, message: string, options: AppErrorOptions = {}) {
    super(message, { code: ErrorCode.AUTH_ERROR, httpStatus: 401, retryable: false, ...options });
    this.platform = platform;
  }
}

export class RateLimitError extends AppError {
  readonly platform: string;
  constructor(platform: string, message: string, retryAfterMs: number, context?: Record<string, unknown>) {
    super(message, {
      code: ErrorCode.RATE_LIMIT,
      httpStatus: 429,
      retryable: true,
      retryAfterMs,
      ...(context ? { context } : {}),
    });
    this.platform = platform;
  }
}

/**
 * The requested operation is not offered by this platform's official API.
 * Thrown rather than silently no-op'ing, so a caller can never believe a
 * post was deleted when the API has no delete.
 */
export class CapabilityNotSupportedError extends AppError {
  constructor(platform: string, capability: string, reason: string) {
    super(`NOT SUPPORTED BY CURRENT API: ${platform} does not support "${capability}". ${reason}`, {
      code: ErrorCode.CAPABILITY_NOT_SUPPORTED,
      httpStatus: 501,
      retryable: false,
      context: { platform, capability, reason },
    });
  }
}

/** A provider interface exists but no credentials were configured. Explicitly NOT
 *  a silent fallback to fake output. */
export class ProviderNotConfiguredError extends AppError {
  constructor(providerKind: string, envVars: string[]) {
    super(
      `${providerKind} provider is not configured. Set ${envVars.join(', ')} in your environment.`,
      {
        code: ErrorCode.PROVIDER_NOT_CONFIGURED,
        httpStatus: 503,
        retryable: false,
        context: { providerKind, envVars },
      },
    );
  }
}

export class BudgetExceededError extends AppError {
  constructor(window: 'daily' | 'monthly', spentUsd: number, limitUsd: number) {
    super(
      `${window} AI budget exceeded: $${spentUsd.toFixed(2)} of $${limitUsd.toFixed(2)}. Generation halted.`,
      {
        code: ErrorCode.BUDGET_EXCEEDED,
        httpStatus: 402,
        retryable: false,
        context: { window, spentUsd, limitUsd },
      },
    );
  }
}

export class ValidationError extends AppError {
  constructor(message: string, context?: Record<string, unknown>) {
    super(message, {
      code: ErrorCode.VALIDATION_ERROR,
      httpStatus: 400,
      retryable: false,
      ...(context ? { context } : {}),
    });
  }
}

export class PolicyBlockedError extends AppError {
  constructor(message: string, context?: Record<string, unknown>) {
    super(message, {
      code: ErrorCode.POLICY_BLOCKED,
      httpStatus: 422,
      retryable: false,
      ...(context ? { context } : {}),
    });
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string, id?: string) {
    super(id ? `${resource} not found: ${id}` : `${resource} not found`, {
      code: ErrorCode.NOT_FOUND,
      httpStatus: 404,
    });
  }
}

export class ForbiddenError extends AppError {
  constructor(message = 'Forbidden') {
    super(message, { code: ErrorCode.FORBIDDEN, httpStatus: 403 });
  }
}

export class AiError extends AppError {
  constructor(message: string, options: AppErrorOptions = {}) {
    super(message, { code: ErrorCode.AI_ERROR, httpStatus: 502, retryable: true, ...options });
  }
}

export function isRetryable(err: unknown): boolean {
  return err instanceof AppError ? err.retryable : false;
}

export function retryAfterOf(err: unknown): number | undefined {
  return err instanceof AppError ? err.retryAfterMs : undefined;
}
