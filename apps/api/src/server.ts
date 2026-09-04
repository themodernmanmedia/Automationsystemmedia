/**
 * API server.
 */
import Fastify from 'fastify';
import cookie from '@fastify/cookie';
import cors from '@fastify/cors';
import helmet from '@fastify/helmet';
import rateLimit from '@fastify/rate-limit';
import { ZodError } from 'zod';
import { AppError, getConfig } from '@mmos/core';
import { disconnect } from '@mmos/db';
import { createContext, type AppContext } from './context.js';
import { authRoutes } from './routes/auth.js';
import { oauthRoutes } from './routes/oauth.js';
import { automationRoutes } from './routes/automation.js';
import { contentRoutes } from './routes/content.js';
import { miscRoutes } from './routes/misc.js';
import { experimentRoutes } from './routes/experiments.js';

export async function buildServer(ctx: AppContext = createContext()) {
  const app = Fastify({ logger: false, trustProxy: true, bodyLimit: 10 * 1024 * 1024 });

  await app.register(helmet, {
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        imgSrc: ["'self'", 'data:', 'https:'],
        scriptSrc: ["'self'"],
        objectSrc: ["'none'"],
        frameAncestors: ["'none'"],
      },
    },
    hsts: ctx.config.NODE_ENV === 'production' ? { maxAge: 31_536_000, includeSubDomains: true } : false,
  });

  // The dashboard sends credentials, so the origin must be exact — a wildcard
  // is not permitted with credentials and would be unsafe here regardless.
  await app.register(cors, { origin: ctx.config.WEB_BASE_URL, credentials: true });
  await app.register(cookie, { secret: ctx.config.SESSION_SECRET });
  await app.register(rateLimit, {
    global: true,
    max: 300,
    timeWindow: '1 minute',
    keyGenerator: (req) => req.ip,
  });

  /**
   * Single error boundary. Validation and typed application errors get a clean
   * response; anything unrecognized is logged in full and returned as a bare
   * 500, so an internal detail cannot leak through an unexpected error shape.
   */
  app.setErrorHandler((error, request, reply) => {
    if (error instanceof ZodError) {
      return reply.code(400).send({
        error: 'ValidationError',
        code: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        issues: error.issues.map((i) => ({ path: i.path.join('.'), message: i.message })),
      });
    }
    if (error instanceof AppError) {
      if (error.httpStatus >= 500) {
        ctx.logger.error({ err: error, url: request.url }, 'request failed');
      } else {
        ctx.logger.warn({ code: error.code, url: request.url, message: error.message }, 'request rejected');
      }
      return reply.code(error.httpStatus).send(error.toPublicJSON());
    }
    if ((error as { statusCode?: number }).statusCode === 429) {
      return reply.code(429).send({ error: 'RateLimit', code: 'RATE_LIMIT', message: 'Too many requests' });
    }

    ctx.logger.error({ err: error, url: request.url }, 'unhandled error');
    return reply.code(500).send({
      error: 'InternalError',
      code: 'INTERNAL',
      message: 'An unexpected error occurred',
    });
  });

  app.setNotFoundHandler((request, reply) => {
    return reply.code(404).send({ error: 'NotFound', code: 'NOT_FOUND', message: `No route for ${request.method} ${request.url}` });
  });

  /** Auth endpoints get a much tighter limit — this is where guessing happens. */
  await app.register(async (scoped) => {
    await scoped.register(rateLimit, { max: 10, timeWindow: '1 minute' });
    await authRoutes(scoped, ctx);
  }, { prefix: '/api' });

  await app.register(async (scoped) => {
    await oauthRoutes(scoped, ctx);
    await automationRoutes(scoped, ctx);
    await contentRoutes(scoped, ctx);
    await miscRoutes(scoped, ctx);
    await experimentRoutes(scoped, ctx);
  }, { prefix: '/api' });

  return app;
}

async function main(): Promise<void> {
  const config = getConfig();
  const ctx = createContext(config);
  const app = await buildServer(ctx);

  const shutdown = async (signal: string) => {
    ctx.logger.info({ signal }, 'shutting down');
    await app.close();
    await disconnect();
    process.exit(0);
  };
  process.on('SIGTERM', () => void shutdown('SIGTERM'));
  process.on('SIGINT', () => void shutdown('SIGINT'));

  await app.listen({ port: config.API_PORT, host: '0.0.0.0' });

  ctx.logger.info(
    { port: config.API_PORT, integrations: ctx.integrations },
    'Modern Man OS API listening',
  );
  for (const [key, message] of Object.entries(ctx.integrationErrors)) {
    ctx.logger.warn({ integration: key }, message);
  }
}

// Only auto-start when run directly, so tests can import buildServer.
if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split('/').pop() ?? '')) {
  main().catch((err) => {
    console.error('Failed to start API server:', err);
    process.exit(1);
  });
}
