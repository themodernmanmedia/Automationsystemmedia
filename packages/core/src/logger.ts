/** Structured logging. JSON in production so logs are queryable; pretty in dev. */
import { pino, type Logger } from 'pino';

const REDACT_PATHS = [
  'accessToken', 'refreshToken', 'access_token', 'refresh_token',
  'password', 'client_secret', 'clientSecret', 'apiKey', 'api_key',
  'authorization', 'cookie',
  '*.accessToken', '*.refreshToken', '*.password', '*.apiKey',
  'req.headers.authorization', 'req.headers.cookie',
];

export function createLogger(opts: { level?: string; name?: string; pretty?: boolean } = {}): Logger {
  return pino({
    name: opts.name ?? 'mmos',
    level: opts.level ?? 'info',
    redact: { paths: REDACT_PATHS, censor: '[REDACTED]' },
    formatters: { level: (label) => ({ level: label }) },
    timestamp: pino.stdTimeFunctions.isoTime,
    ...(opts.pretty
      ? { transport: { target: 'pino-pretty', options: { colorize: true, translateTime: 'HH:MM:ss' } } }
      : {}),
  });
}

export const logger: Logger = createLogger({
  level: process.env.LOG_LEVEL ?? 'info',
  pretty: process.env.NODE_ENV === 'development',
});

export type { Logger };
