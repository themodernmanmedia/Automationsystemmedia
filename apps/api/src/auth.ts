/**
 * Sessions and RBAC.
 *
 * Session tokens are random 256-bit values; only their hash is stored, so a
 * database leak does not hand an attacker live sessions. The cookie is
 * httpOnly, so script on the page cannot read it.
 */
import { createHash } from 'node:crypto';
import type { FastifyReply, FastifyRequest } from 'fastify';
import { ForbiddenError, randomToken, type Config } from '@mmos/core';
import { prisma } from '@mmos/db';

export const SESSION_COOKIE = 'mmos_session';
const SESSION_TTL_MS = 7 * 24 * 3_600_000;

export type Role = 'OWNER' | 'ADMIN' | 'EDITOR' | 'VIEWER';

/** Higher number outranks lower. Used for "at least this role" checks. */
const ROLE_RANK: Record<Role, number> = { VIEWER: 0, EDITOR: 1, ADMIN: 2, OWNER: 3 };

export interface AuthenticatedUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  organizationId: string;
}

declare module 'fastify' {
  interface FastifyRequest {
    user?: AuthenticatedUser;
  }
}

function hashToken(token: string): string {
  return createHash('sha256').update(token).digest('hex');
}

export async function createSession(
  userId: string,
  meta: { ipAddress?: string; userAgent?: string },
): Promise<{ token: string; expiresAt: Date }> {
  const token = randomToken(32);
  const expiresAt = new Date(Date.now() + SESSION_TTL_MS);
  await prisma.session.create({
    data: {
      userId,
      tokenHash: hashToken(token),
      expiresAt,
      ipAddress: meta.ipAddress ?? null,
      userAgent: meta.userAgent ?? null,
    },
  });
  return { token, expiresAt };
}

export async function resolveSession(token: string): Promise<AuthenticatedUser | null> {
  const session = await prisma.session.findUnique({
    where: { tokenHash: hashToken(token) },
    include: { user: true },
  });
  if (!session || session.revokedAt || session.expiresAt < new Date()) return null;
  if (!session.user.isActive) return null;
  return {
    id: session.user.id,
    email: session.user.email,
    name: session.user.name,
    role: session.user.role as Role,
    organizationId: session.user.organizationId,
  };
}

export async function revokeSession(token: string): Promise<void> {
  await prisma.session.updateMany({
    where: { tokenHash: hashToken(token) },
    data: { revokedAt: new Date() },
  });
}

export function setSessionCookie(reply: FastifyReply, token: string, expiresAt: Date, config: Config): void {
  reply.setCookie(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: config.NODE_ENV === 'production',
    path: '/',
    expires: expiresAt,
  });
}

export function clearSessionCookie(reply: FastifyReply): void {
  reply.clearCookie(SESSION_COOKIE, { path: '/' });
}

/** Route guard. `minRole` enforces "at least this role". */
export function requireAuth(minRole: Role = 'VIEWER') {
  return async (request: FastifyRequest): Promise<void> => {
    const token = request.cookies[SESSION_COOKIE];
    if (!token) throw new ForbiddenError('Authentication required');

    const user = await resolveSession(token);
    if (!user) throw new ForbiddenError('Session is invalid or expired');

    if (ROLE_RANK[user.role] < ROLE_RANK[minRole]) {
      throw new ForbiddenError(`This action requires the ${minRole} role or higher.`);
    }
    request.user = user;
  };
}

/**
 * Every organization-scoped query goes through this rather than each handler
 * remembering to add a `where`. Forgetting a tenant filter in a multi-tenant
 * system is a data breach, so it must not be a thing a handler can forget.
 */
export function orgScope(request: FastifyRequest): { organizationId: string } {
  if (!request.user) throw new ForbiddenError('Authentication required');
  return { organizationId: request.user.organizationId };
}
