/**
 * Global test setup.
 *
 * Three jobs:
 *  1. Put the root `.env` into `process.env`, so the suites that exercise real
 *     Postgres and Redis find DATABASE_URL and REDIS_URL. Vitest runs from the
 *     repository root but nothing else loads the file, and CI sets these
 *     directly — which a real environment variable winning keeps intact.
 *  2. Guarantee no test can reach a real social platform. The brief is explicit
 *     that production accounts must never be used in tests, so this is enforced
 *     mechanically rather than by convention.
 *  3. Neutralize any ambient HTTP proxy, which would otherwise intercept
 *     requests before nock ever sees them.
 */
import { afterAll, beforeAll } from 'vitest';
import nock from 'nock';
import { loadDotEnv } from '@mmos/core';

// `.env.test` first, so a developer can point the suite at a throwaway
// database without touching the `.env` the app runs from.
loadDotEnv(process.cwd(), ['.env.test', '.env']);

/**
 * Refuse to run against a database that is not obviously disposable.
 *
 * The API suite truncates every table — registration is single-use, so it has
 * to start from zero organizations. Pointed at a development database that is
 * one destroyed dataset, and `pnpm test` after filling in `.env` is exactly how
 * someone would find that out. Requiring the name to say `test` costs one line
 * of configuration and removes the possibility.
 */
const databaseUrl = process.env['DATABASE_URL'];
if (databaseUrl && !/test/i.test(new URL(databaseUrl).pathname)) {
  throw new Error(
    `Refusing to run tests against "${new URL(databaseUrl).pathname.slice(1)}": the suite truncates every table.\n` +
      'Create a disposable database and point the suite at it, e.g.\n' +
      '  createdb mmos_test\n' +
      '  echo \'DATABASE_URL=postgresql://mmos:mmos@localhost:5432/mmos_test?schema=public\' > .env.test',
  );
}

const PROXY_VARS = [
  'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
  'GLOBAL_AGENT_HTTP_PROXY', 'GLOBAL_AGENT_HTTPS_PROXY',
];
for (const v of PROXY_VARS) delete process.env[v];

/** Hostnames a test must never contact. Reaching one is a suite failure. */
const FORBIDDEN_HOSTS = [
  'graph.facebook.com',
  'graph.instagram.com',
  'open.tiktokapis.com',
  'api.anthropic.com',
  'api.openai.com',
];

beforeAll(() => {
  nock.disableNetConnect();
  // Allow loopback so integration tests can use a local Postgres/Redis.
  nock.enableNetConnect((host) => /^(localhost|127\.0\.0\.1|::1)(:\d+)?$/.test(host));

  nock.emitter.on('no match', (req: unknown) => {
    const host = (req as { host?: string; hostname?: string })?.host ?? (req as { hostname?: string })?.hostname ?? '';
    if (FORBIDDEN_HOSTS.some((h) => String(host).includes(h))) {
      throw new Error(
        `Test attempted to contact a real platform host: ${host}. All platform HTTP must be mocked.`,
      );
    }
  });
});

afterAll(() => {
  nock.cleanAll();
  nock.enableNetConnect();
});
