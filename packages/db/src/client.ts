import { PrismaClient } from '@prisma/client';

/**
 * A single PrismaClient per process. Cached on globalThis so Next.js dev
 * hot-reload does not open a new pool on every edit and exhaust Postgres
 * connections.
 */
const globalForPrisma = globalThis as unknown as { __mmosPrisma?: PrismaClient };

export const prisma: PrismaClient =
  globalForPrisma.__mmosPrisma ??
  new PrismaClient({
    log:
      process.env.NODE_ENV === 'development'
        ? [{ level: 'warn', emit: 'stdout' }, { level: 'error', emit: 'stdout' }]
        : [{ level: 'error', emit: 'stdout' }],
  });

if (process.env.NODE_ENV !== 'production') globalForPrisma.__mmosPrisma = prisma;

export async function disconnect(): Promise<void> {
  await prisma.$disconnect();
}

/** Liveness probe used by the health endpoint. */
export async function healthcheck(): Promise<{ ok: boolean; latencyMs: number; error?: string }> {
  const start = Date.now();
  try {
    await prisma.$queryRaw`SELECT 1`;
    return { ok: true, latencyMs: Date.now() - start };
  } catch (err) {
    return { ok: false, latencyMs: Date.now() - start, error: (err as Error).message };
  }
}
