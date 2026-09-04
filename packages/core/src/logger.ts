/** Structured logging. JSON in production so logs are queryable; pretty in dev. */
import { createRequire } from 'node:module';
import { pino, stdSerializers, type Logger } from 'pino';

const require = createRequire(import.meta.url);

const REDACT_PATHS = [
  'accessToken', 'refreshToken', 'access_token', 'refresh_token',
  'password', 'client_secret', 'clientSecret', 'apiKey', 'api_key',
  'authorization', 'cookie',
  '*.accessToken', '*.refreshToken', '*.password', '*.apiKey',
  'req.headers.authorization', 'req.headers.cookie',
];

/**
 * Second line of defence, for credentials that are inside a string rather than
 * under a key.
 *
 * `redact.paths` matches key paths, so it never inspects a value — a token
 * embedded in a URL passes straight through it. That is not hypothetical: an
 * error context carrying a request URL is exactly how a live access token
 * reached the logs once already. Anything credential-shaped in a query string
 * or in URL userinfo is scrubbed here regardless of which key holds it.
 */
const SECRET_IN_STRING =
  /([?&][^?&=\s]*(?:token|secret|password|credential|signature|apikey|api_key|auth|key|code)[^?&=\s]*=)([^&\s"']+)/gi;
const USERINFO_IN_STRING = /(\b[a-z][a-z0-9+.-]*:\/\/)[^/@\s]+@/gi;

export function scrubSecrets(value: string): string {
  return value.replace(SECRET_IN_STRING, '$1[REDACTED]').replace(USERINFO_IN_STRING, '$1[REDACTED]@');
}

/** Applies `scrubSecrets` to every string reachable in a log payload. */
function deepScrub(value: unknown, seen: WeakSet<object>, depth = 0): unknown {
  if (typeof value === 'string') return scrubSecrets(value);
  if (depth >= 8 || value === null || typeof value !== 'object') return value;
  if (seen.has(value)) return value;
  seen.add(value);
  if (Array.isArray(value)) return value.map((v) => deepScrub(v, seen, depth + 1));
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    out[k] = deepScrub(v, seen, depth + 1);
  }
  return out;
}

/**
 * pino's default error serializer copies an error's own enumerable properties,
 * which includes `AppError.context` — `readonly` is a compile-time annotation
 * with no runtime effect. So the context travels into the log line and has to
 * be scrubbed on the way.
 */
export function errorSerializer(err: Error): unknown {
  return deepScrub(stdSerializers.err(err as Error & { code?: number }), new WeakSet());
}

/**
 * pino-pretty is a dev-only transport. If it is missing (a production install
 * that pruned devDependencies), fall back to JSON rather than refusing to boot
 * — a logging preference must never be able to take the service down.
 */
function prettyTransport(): object | undefined {
  try {
    require.resolve('pino-pretty');
    return { transport: { target: 'pino-pretty', options: { colorize: true, translateTime: 'HH:MM:ss' } } };
  } catch {
    return undefined;
  }
}

export interface LoggerOptions {
  level?: string;
  name?: string;
  pretty?: boolean;
  /** Alternative sink. Tests use it to assert on what is actually emitted. */
  destination?: NodeJS.WritableStream;
}

export function createLogger(opts: LoggerOptions = {}): Logger {
  const config = {
    name: opts.name ?? 'mmos',
    level: opts.level ?? 'info',
    redact: { paths: REDACT_PATHS, censor: '[REDACTED]' },
    serializers: { err: errorSerializer, error: errorSerializer },
    formatters: { level: (label: string) => ({ level: label }) },
    timestamp: pino.stdTimeFunctions.isoTime,
    // A transport and an explicit destination are mutually exclusive in pino.
    ...(opts.destination ? {} : opts.pretty ? (prettyTransport() ?? {}) : {}),
  };
  return opts.destination ? pino(config, opts.destination) : pino(config);
}

export const logger: Logger = createLogger({
  level: process.env.LOG_LEVEL ?? 'info',
  pretty: process.env.NODE_ENV === 'development',
});

export type { Logger };
