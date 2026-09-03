/**
 * API integration tests against real Postgres.
 *
 * These exercise the boundaries that matter most: authentication, tenant
 * isolation, the RBAC guards on destructive controls, and the promise that
 * token material never leaves the server.
 */
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { prisma, TokenStore } from '@mmos/db';
import { loadConfig } from '@mmos/core';
import { buildServer } from './server.js';
import { createContext } from './context.js';
import type { FastifyInstance } from 'fastify';

const TEST_ENV = {
  ...process.env,
  NODE_ENV: 'test',
  LOG_LEVEL: 'silent',
  DATABASE_URL: process.env['DATABASE_URL'] ?? 'postgresql://mmos:mmos@localhost:5432/mmos?schema=public',
  REDIS_URL: 'redis://localhost:6379',
  ENCRYPTION_KEY: Buffer.alloc(32, 7).toString('base64'),
  SESSION_SECRET: Buffer.alloc(32, 9).toString('base64'),
};

let app: FastifyInstance;
let ownerCookie: string;
let organizationId: string;

/** Truncates every table so a rerun starts clean. */
async function resetDatabase(): Promise<void> {
  await prisma.$executeRawUnsafe(`
    TRUNCATE TABLE
      audit_logs, agent_errors, agent_runs, cost_entries, analytics_records,
      performance_snapshots, publishing_attempts, publishing_jobs, qa_results,
      content_scores, content_status_changes, carousel_slides, carousel_posts,
      reels, captions, media_assets, audio_assets, content_pieces, content_ideas,
      research_reports, claims, sources, topics, platform_tokens, social_accounts,
      brands, automation_states, system_memories, experiments, sessions, users,
      organizations
    RESTART IDENTITY CASCADE
  `);
}

beforeAll(async () => {
  const config = loadConfig(TEST_ENV as NodeJS.ProcessEnv);
  await resetDatabase();
  app = await buildServer(createContext(config));
  await app.ready();

  const register = await app.inject({
    method: 'POST',
    url: '/api/auth/register',
    payload: {
      email: 'owner@themodernman.test',
      password: 'a-very-long-test-password',
      name: 'Owner',
      organizationName: 'The Modern Man',
    },
  });
  expect(register.statusCode).toBe(201);
  organizationId = register.json().organization.id;
  ownerCookie = extractCookie(register.headers['set-cookie']);
});

afterAll(async () => {
  await app?.close();
  await resetDatabase();
  await prisma.$disconnect();
});

function extractCookie(header: string | string[] | undefined): string {
  const raw = Array.isArray(header) ? header[0] : header;
  return raw?.split(';')[0] ?? '';
}

describe('health', () => {
  it('reports database health and which integrations are configured', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/health' });
    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.status).toBe('healthy');
    expect(body.checks.database.ok).toBe(true);
    // Honest reporting: nothing is configured in the test environment.
    expect(body.integrations).toHaveProperty('meta');
    expect(body.integrations.meta).toBe(false);
  });
});

describe('authentication', () => {
  it('refuses a second registration so an exposed instance cannot be joined', async () => {
    const res = await app.inject({
      method: 'POST',
      url: '/api/auth/register',
      payload: {
        email: 'other@test.com',
        password: 'another-long-password',
        name: 'Other',
        organizationName: 'Other Org',
      },
    });
    expect(res.statusCode).toBe(403);
  });

  it('rejects unauthenticated access to protected routes', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/overview' });
    expect(res.statusCode).toBe(403);
  });

  it('gives the same response for an unknown email and a wrong password', async () => {
    const unknown = await app.inject({
      method: 'POST',
      url: '/api/auth/login',
      payload: { email: 'nobody@test.com', password: 'wrong-password-here' },
    });
    const wrong = await app.inject({
      method: 'POST',
      url: '/api/auth/login',
      payload: { email: 'owner@themodernman.test', password: 'wrong-password-here' },
    });
    // Identical, so the endpoint cannot be used to enumerate accounts.
    expect(unknown.statusCode).toBe(wrong.statusCode);
    expect(unknown.json().message).toBe(wrong.json().message);
  });

  it('authenticates the owner', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/auth/me', headers: { cookie: ownerCookie } });
    expect(res.statusCode).toBe(200);
    expect(res.json().user.role).toBe('OWNER');
  });

  it('rejects a malformed registration payload', async () => {
    const res = await app.inject({
      method: 'POST',
      url: '/api/auth/register',
      payload: { email: 'not-an-email', password: 'short' },
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().code).toBe('VALIDATION_ERROR');
  });
});

describe('RBAC', () => {
  let viewerCookie: string;

  beforeAll(async () => {
    await app.inject({
      method: 'POST',
      url: '/api/auth/users',
      headers: { cookie: ownerCookie },
      payload: { email: 'viewer@test.com', password: 'viewer-long-password', name: 'Viewer', role: 'VIEWER' },
    });
    const login = await app.inject({
      method: 'POST',
      url: '/api/auth/login',
      payload: { email: 'viewer@test.com', password: 'viewer-long-password' },
    });
    viewerCookie = extractCookie(login.headers['set-cookie']);
  });

  it('lets a viewer read', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/overview', headers: { cookie: viewerCookie } });
    expect(res.statusCode).toBe(200);
  });

  it('forbids a viewer from engaging the kill switch', async () => {
    const res = await app.inject({
      method: 'POST',
      url: '/api/automation/kill',
      headers: { cookie: viewerCookie },
      payload: { engaged: true },
    });
    expect(res.statusCode).toBe(403);
  });

  it('forbids a viewer from clearing the queue', async () => {
    const res = await app.inject({
      method: 'POST',
      url: '/api/automation/queue/clear',
      headers: { cookie: viewerCookie },
      payload: {},
    });
    expect(res.statusCode).toBe(403);
  });
});

describe('automation controls', () => {
  it('engages and releases the kill switch', async () => {
    const on = await app.inject({
      method: 'POST',
      url: '/api/automation/kill',
      headers: { cookie: ownerCookie },
      payload: { engaged: true },
    });
    expect(on.json().killSwitch).toBe(true);

    const state = await app.inject({ method: 'GET', url: '/api/automation', headers: { cookie: ownerCookie } });
    expect(state.json().state.killSwitch).toBe(true);

    await app.inject({
      method: 'POST',
      url: '/api/automation/kill',
      headers: { cookie: ownerCookie },
      payload: { engaged: false },
    });
  });

  it('records every kill-switch change in the audit log', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/logs/audit', headers: { cookie: ownerCookie } });
    const actions = res.json().logs.map((l: { action: string }) => l.action);
    expect(actions).toContain('kill_switch_engaged');
    expect(actions).toContain('kill_switch_released');
  });

  it('refuses autonomous mode when no LLM provider is configured', async () => {
    const res = await app.inject({
      method: 'POST',
      url: '/api/automation/autonomous',
      headers: { cookie: ownerCookie },
      payload: { enabled: true },
    });
    // Rather than letting it look enabled while producing only errors.
    expect(res.json().error).toMatch(/no LLM provider is configured/i);
  });

  it('reports an empty queue as critical', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/automation', headers: { cookie: ownerCookie } });
    expect(res.json().queue.status).toBe('CRITICAL');
    expect(res.json().queue.shouldGenerate).toBe(true);
  });
});

describe('platform capabilities', () => {
  it('serves the matrix with reasons for missing capabilities', async () => {
    const res = await app.inject({
      method: 'GET',
      url: '/api/platforms/capabilities',
      headers: { cookie: ownerCookie },
    });
    const body = res.json();
    expect(body.matrix['Native scheduling'].INSTAGRAM.supported).toBe(false);
    expect(body.matrix['Native scheduling'].FACEBOOK.supported).toBe(true);
    // The UI needs the reason, not just a false.
    expect(body.matrix['Native scheduling'].INSTAGRAM.note).toMatch(/scheduled_publish_time/);
    expect(body.matrix['Delete post'].INSTAGRAM.note).toMatch(/NOT SUPPORTED BY CURRENT API/);
    expect(body.planned).toContain('YOUTUBE');
  });
});

describe('token confidentiality', () => {
  it('never returns token material through the accounts endpoint', async () => {
    const account = await prisma.socialAccount.create({
      data: {
        organizationId,
        platform: 'INSTAGRAM',
        platformAccountId: 'ig-test-1',
        username: 'themodernman',
        status: 'CONNECTED',
        scopes: ['instagram_business_content_publish'],
      },
    });
    const tokens = new TokenStore(TEST_ENV.ENCRYPTION_KEY);
    await tokens.store({
      socialAccountId: account.id,
      accessToken: 'SUPER-SECRET-TOKEN-VALUE',
      expiresAt: new Date(Date.now() + 30 * 86_400_000),
    });

    const res = await app.inject({ method: 'GET', url: '/api/accounts', headers: { cookie: ownerCookie } });
    const raw = res.body;

    expect(res.statusCode).toBe(200);
    // The whole response body, not just the parsed fields we expect.
    expect(raw).not.toContain('SUPER-SECRET-TOKEN-VALUE');
    expect(raw).not.toContain('accessTokenEnc');

    const returned = res.json().accounts[0];
    expect(returned.username).toBe('themodernman');
    expect(returned.tokenStatus).toBe('VALID');
    // Capabilities travel with the account so the UI can disable what cannot work.
    expect(returned.capabilities.canSchedule).toBe(false);
    expect(returned.capabilities.canDelete).toBe(false);
  });

  it('stores the token encrypted, not in plaintext', async () => {
    const row = await prisma.platformToken.findFirst();
    expect(row!.accessTokenEnc).not.toContain('SUPER-SECRET-TOKEN-VALUE');
    expect(row!.accessTokenEnc.startsWith('v1:')).toBe(true);
  });

  it('warns that TikTok posts are private before the client is audited', async () => {
    await prisma.socialAccount.create({
      data: {
        organizationId,
        platform: 'TIKTOK',
        platformAccountId: 'tt-test-1',
        username: 'themodernman',
        status: 'CONNECTED',
        isAudited: false,
        scopes: ['video.publish'],
      },
    });
    const res = await app.inject({ method: 'GET', url: '/api/accounts', headers: { cookie: ownerCookie } });
    const tiktok = res.json().accounts.find((a: { platform: string }) => a.platform === 'TIKTOK');
    expect(tiktok.auditWarning).toMatch(/AUDIT PENDING/);
  });
});

describe('error handling', () => {
  it('returns a structured 404 for an unknown route', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/nope', headers: { cookie: ownerCookie } });
    expect(res.statusCode).toBe(404);
    expect(res.json().code).toBe('NOT_FOUND');
  });

  it('returns a typed 404 for a missing resource', async () => {
    const res = await app.inject({
      method: 'GET',
      url: '/api/content/does-not-exist',
      headers: { cookie: ownerCookie },
    });
    expect(res.statusCode).toBe(404);
  });
});
