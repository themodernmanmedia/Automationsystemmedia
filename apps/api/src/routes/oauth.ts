/**
 * OAuth connection flows.
 *
 * The `state` parameter is a signed, TTL-bounded value and is the CSRF defense
 * for the callback. It is verified before any token exchange — a callback
 * without a valid state is never allowed to attach an account.
 *
 * Tokens are exchanged server-side only; the authorization code never reaches
 * the browser, and token material is never returned by any endpoint.
 */
import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { ForbiddenError, NotFoundError, ValidationError, signValue, verifySignedValue } from '@mmos/core';
import { prisma } from '@mmos/db';
import { FacebookAdapter, type PlatformName } from '@mmos/platforms';
import type { AppContext } from '../context.js';
import { requireAuth, orgScope } from '../auth.js';

const STATE_TTL_MS = 10 * 60_000;

function buildState(organizationId: string, userId: string, platform: string, secret: string): string {
  return signValue(JSON.stringify({ organizationId, userId, platform, ts: Date.now() }), secret);
}

function parseState(state: string, secret: string): { organizationId: string; userId: string; platform: string } {
  const raw = verifySignedValue(state, secret);
  if (!raw) throw new ForbiddenError('OAuth state signature is invalid. The request may have been tampered with.');

  const parsed = JSON.parse(raw) as { organizationId: string; userId: string; platform: string; ts: number };
  if (Date.now() - parsed.ts > STATE_TTL_MS) {
    throw new ForbiddenError('OAuth state has expired. Start the connection again.');
  }
  return parsed;
}

export async function oauthRoutes(app: FastifyInstance, ctx: AppContext): Promise<void> {
  /** Which platforms can actually be connected, and why not when they cannot. */
  app.get('/oauth/providers', { preHandler: requireAuth() }, async () => {
    const configured = ctx.adapters.configured();
    return {
      providers: (['INSTAGRAM', 'FACEBOOK', 'TIKTOK'] as PlatformName[]).map((platform) => ({
        platform,
        available: configured.includes(platform),
        reason: configured.includes(platform)
          ? undefined
          : platform === 'TIKTOK'
            ? 'TikTok credentials are not configured. Set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET and TIKTOK_REDIRECT_URI.'
            : 'Meta credentials are not configured. Set META_APP_ID, META_APP_SECRET and META_REDIRECT_URI.',
      })),
    };
  });

  app.get('/oauth/:platform/start', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const { platform } = z
      .object({ platform: z.enum(['instagram', 'facebook', 'tiktok']) })
      .parse(request.params);
    const platformName = platform.toUpperCase() as PlatformName;

    const adapter = ctx.adapters.get(platformName);
    const user = request.user!;
    const state = buildState(user.organizationId, user.id, platformName, ctx.config.SESSION_SECRET);

    return { authorizationUrl: adapter.getAuthorizationUrl(state) };
  });

  /**
   * Meta callback. Instagram and Facebook share one app, so one callback
   * handles both: the user token is exchanged, then Pages are enumerated and
   * each Page's own token is stored, since publishing uses the Page token.
   */
  app.get('/oauth/meta/callback', async (request, reply) => {
    const query = z
      .object({ code: z.string().optional(), state: z.string(), error_description: z.string().optional() })
      .parse(request.query);

    if (!query.code) {
      throw new ValidationError(query.error_description ?? 'Authorization was denied.');
    }

    const { organizationId, userId, platform } = parseState(query.state, ctx.config.SESSION_SECRET);
    const adapter = ctx.adapters.get(platform as PlatformName);
    const tokens = await adapter.exchangeCodeForTokens(query.code);

    const connected: Array<{ id: string; platform: string; username: string }> = [];

    if (platform === 'FACEBOOK' && adapter instanceof FacebookAdapter) {
      const pages = await adapter.listPages(tokens.accessToken);
      if (pages.length === 0) {
        throw new ValidationError(
          'No Facebook Pages are available on this account. A Page is required to publish.',
        );
      }
      for (const page of pages) {
        const account = await upsertAccount(organizationId, 'FACEBOOK', {
          platformAccountId: page.id,
          username: page.name,
          displayName: page.name,
          accountType: 'PAGE',
          scopes: tokens.scopes,
        });
        // Page tokens, not the user token: publishing requires the Page token.
        await ctx.tokens.store({
          socialAccountId: account.id,
          accessToken: page.accessToken,
          expiresAt: tokens.expiresAt ?? null,
          scopes: tokens.scopes,
        });
        connected.push({ id: account.id, platform: 'FACEBOOK', username: page.name });
      }
    } else {
      const profile = await adapter.getAccount({
        accessToken: tokens.accessToken,
        platformAccountId: 'me',
      });
      const account = await upsertAccount(organizationId, platform as PlatformName, {
        platformAccountId: profile.platformAccountId,
        username: profile.username,
        displayName: profile.displayName ?? null,
        profileImageUrl: profile.profileImageUrl ?? null,
        accountType: profile.accountType ?? null,
        scopes: tokens.scopes,
      });
      await ctx.tokens.store({
        socialAccountId: account.id,
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken ?? null,
        expiresAt: tokens.expiresAt ?? null,
        scopes: tokens.scopes,
      });
      connected.push({ id: account.id, platform, username: profile.username });
    }

    await prisma.auditLog.create({
      data: {
        organizationId,
        actorType: 'user',
        actorId: userId,
        action: 'connect_account',
        diff: { platform, accounts: connected.map((c) => c.username) },
        ipAddress: request.ip,
      },
    });

    return reply.redirect(`${ctx.config.WEB_BASE_URL}/accounts?connected=${platform.toLowerCase()}`);
  });

  app.get('/oauth/tiktok/callback', async (request, reply) => {
    const query = z
      .object({ code: z.string().optional(), state: z.string(), error_description: z.string().optional() })
      .parse(request.query);

    if (!query.code) throw new ValidationError(query.error_description ?? 'Authorization was denied.');

    const { organizationId, userId } = parseState(query.state, ctx.config.SESSION_SECRET);
    const adapter = ctx.adapters.get('TIKTOK');
    const tokens = await adapter.exchangeCodeForTokens(query.code);
    const profile = await adapter.getAccount({
      accessToken: tokens.accessToken,
      platformAccountId: 'me',
    });

    const account = await upsertAccount(organizationId, 'TIKTOK', {
      platformAccountId: profile.platformAccountId,
      username: profile.username,
      displayName: profile.displayName ?? null,
      profileImageUrl: profile.profileImageUrl ?? null,
      accountType: 'CREATOR',
      scopes: tokens.scopes,
      // Audit status is set by a human once TikTok approves the client. Until
      // then the account card warns that posts will be private.
      statusMessage:
        'Until this API client passes TikTok audit, all posts are restricted to SELF_ONLY (private) visibility.',
    });

    await ctx.tokens.store({
      socialAccountId: account.id,
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken ?? null,
      expiresAt: tokens.expiresAt ?? null,
      refreshExpiresAt: tokens.refreshExpiresAt ?? null,
      scopes: tokens.scopes,
    });

    await prisma.auditLog.create({
      data: {
        organizationId,
        actorType: 'user',
        actorId: userId,
        action: 'connect_account',
        diff: { platform: 'TIKTOK', username: profile.username },
        ipAddress: request.ip,
      },
    });

    return reply.redirect(`${ctx.config.WEB_BASE_URL}/accounts?connected=tiktok`);
  });

  /** Disconnecting deletes the stored credentials, not just a status flag. */
  app.delete('/oauth/accounts/:id', { preHandler: requireAuth('ADMIN') }, async (request) => {
    const { id } = z.object({ id: z.string() }).parse(request.params);
    const scope = orgScope(request);

    const account = await prisma.socialAccount.findFirst({ where: { id, ...scope } });
    if (!account) throw new NotFoundError('SocialAccount', id);

    await ctx.tokens.delete(account.id);
    await prisma.socialAccount.update({
      where: { id: account.id },
      data: { status: 'DISCONNECTED', statusMessage: 'Disconnected by user' },
    });
    await prisma.auditLog.create({
      data: {
        organizationId: scope.organizationId,
        actorType: 'user',
        actorId: request.user!.id,
        action: 'disconnect_account',
        subjectType: 'social_account',
        subjectId: account.id,
      },
    });

    return { ok: true };
  });
}

async function upsertAccount(
  organizationId: string,
  platform: PlatformName,
  data: {
    platformAccountId: string;
    username: string;
    displayName?: string | null;
    profileImageUrl?: string | null;
    accountType?: string | null;
    scopes: string[];
    statusMessage?: string;
  },
) {
  return prisma.socialAccount.upsert({
    where: {
      organizationId_platform_platformAccountId: {
        organizationId,
        platform,
        platformAccountId: data.platformAccountId,
      },
    },
    create: {
      organizationId,
      platform,
      platformAccountId: data.platformAccountId,
      username: data.username,
      displayName: data.displayName ?? null,
      profileImageUrl: data.profileImageUrl ?? null,
      accountType: data.accountType ?? null,
      scopes: data.scopes,
      status: 'CONNECTED',
      statusMessage: data.statusMessage ?? null,
    },
    update: {
      username: data.username,
      displayName: data.displayName ?? null,
      profileImageUrl: data.profileImageUrl ?? null,
      scopes: data.scopes,
      status: 'CONNECTED',
      statusMessage: data.statusMessage ?? null,
    },
  });
}
