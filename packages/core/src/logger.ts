/** Structured logging. JSON in production so logs are queryable; pretty in dev. */
import { createRequire } from 'node:module';
import { pino, type Logger } from 'pino';

const require = createRequire(import.meta.url);

const REDACT_PATHS = [
  'accessToken', 'refreshToken', 'access_token', 'refresh_token',
  'password', 'client_secret', 'clientSecret', 'apiKey', 'api_key',
  'authorization', 'cookie',
  '*.accessToken', '*.refreshToken', '*.password', '*.apiKey',
  'req.headers.authorization', 'req.headers.cookie',
];

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

export function createLogger(opts: { level?: string; name?: string; pretty?: boolean } = {}): Logger {
  return pino({
    name: opts.name ?? 'mmos',
    level: opts.level ?? 'info',
    redact: { paths: REDACT_PATHS, censor: '[REDACTED]' },
    formatters: { level: (label) => ({ level: label }) },
    timestamp: pino.stdTimeFunctions.isoTime,
    ...(opts.pretty ? (prettyTransport() ?? {}) : {}),
  });
}

export const logger: Logger = createLogger({
  level: process.env.LOG_LEVEL ?? 'info',
  pretty: process.env.NODE_ENV === 'development',
});

export type { Logger };
