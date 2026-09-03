/**
 * Global test setup.
 *
 * Two jobs:
 *  1. Guarantee no test can reach a real social platform. The brief is explicit
 *     that production accounts must never be used in tests, so this is enforced
 *     mechanically rather than by convention.
 *  2. Neutralize any ambient HTTP proxy, which would otherwise intercept
 *     requests before nock ever sees them.
 */
import { afterAll, beforeAll } from 'vitest';
import nock from 'nock';

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
