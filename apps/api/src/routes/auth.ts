import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { hashPassword, verifyPassword, ForbiddenError, ValidationError } from '@mmos/core';
import { prisma } from '@mmos/db';
import type { AppContext } from '../context.js';
import { clearSessionCookie, createSession, requireAuth, revokeSession, setSessionCookie, SESSION_COOKIE } from '../auth.js';

const loginSchema = z.object({ email: z.string().email(), password: z.string().min(1) });
const registerSchema = z.object({
  email: z.string().email(),
  password: z.string().min(12, 'Password must be at least 12 characters'),
  name: z.string().min(1),
  organizationName: z.string().min(1),
});

export async function authRoutes(app: FastifyInstance, ctx: AppContext): Promise<void> {
  /**
   * Bootstrap registration. Deliberately single-use: it creates the first
   * organization and its OWNER, then refuses. Additional users are invited by
   * an admin, so an exposed instance cannot be joined by a stranger.
   */
  app.post('/auth/register', async (request, reply) => {
    const body = registerSchema.parse(request.body);

    if ((await prisma.organization.count()) > 0) {
      throw new ForbiddenError(
        'This instance is already initialized. Ask an administrator to invite you.',
      );
    }

    const organization = await prisma.organization.create({
      data: { name: body.organizationName, slug: slugify(body.organizationName) },
    });

    const user = await prisma.user.create({
      data: {
        organizationId: organization.id,
        email: body.email.toLowerCase(),
        passwordHash: hashPassword(body.password),
        name: body.name,
        role: 'OWNER',
      },
    });

    const session = await createSession(user.id, {
      ipAddress: request.ip,
      userAgent: request.headers['user-agent'] ?? undefined,
    });
    setSessionCookie(reply, session.token, session.expiresAt, ctx.config);

    await prisma.auditLog.create({
      data: {
        organizationId: organization.id,
        actorType: 'user',
        actorId: user.id,
        action: 'organization_created',
        ipAddress: request.ip,
      },
    });

    return reply.code(201).send({
      user: { id: user.id, email: user.email, name: user.name, role: user.role },
      organization: { id: organization.id, name: organization.name },
    });
  });

  app.post('/auth/login', async (request, reply) => {
    const body = loginSchema.parse(request.body);
    const user = await prisma.user.findUnique({ where: { email: body.email.toLowerCase() } });

    // Identical response for an unknown email and a wrong password, so the
    // endpoint cannot be used to enumerate registered addresses.
    if (!user || !user.isActive || !verifyPassword(body.password, user.passwordHash)) {
      throw new ForbiddenError('Invalid email or password');
    }

    const session = await createSession(user.id, {
      ipAddress: request.ip,
      userAgent: request.headers['user-agent'] ?? undefined,
    });
    setSessionCookie(reply, session.token, session.expiresAt, ctx.config);
    await prisma.user.update({ where: { id: user.id }, data: { lastLoginAt: new Date() } });

    return {
      user: { id: user.id, email: user.email, name: user.name, role: user.role },
    };
  });

  app.post('/auth/logout', async (request, reply) => {
    const token = request.cookies[SESSION_COOKIE];
    if (token) await revokeSession(token);
    clearSessionCookie(reply);
    return { ok: true };
  });

  app.get('/auth/me', { preHandler: requireAuth() }, async (request) => {
    return { user: request.user };
  });

  /** Invite a teammate. Admin+ only, and never able to grant above your own role. */
  app.post('/auth/users', { preHandler: requireAuth('ADMIN') }, async (request, reply) => {
    const body = z
      .object({
        email: z.string().email(),
        password: z.string().min(12),
        name: z.string().min(1),
        role: z.enum(['ADMIN', 'EDITOR', 'VIEWER']),
      })
      .parse(request.body);

    const actor = request.user!;
    if (actor.role !== 'OWNER' && body.role === 'ADMIN') {
      throw new ForbiddenError('Only the owner can create administrators.');
    }
    if (await prisma.user.findUnique({ where: { email: body.email.toLowerCase() } })) {
      throw new ValidationError('A user with that email already exists');
    }

    const user = await prisma.user.create({
      data: {
        organizationId: actor.organizationId,
        email: body.email.toLowerCase(),
        passwordHash: hashPassword(body.password),
        name: body.name,
        role: body.role,
      },
    });

    await prisma.auditLog.create({
      data: {
        organizationId: actor.organizationId,
        actorType: 'user',
        actorId: actor.id,
        action: 'user_created',
        subjectType: 'user',
        subjectId: user.id,
        diff: { role: body.role },
      },
    });

    return reply.code(201).send({ id: user.id, email: user.email, name: user.name, role: user.role });
  });
}

function slugify(name: string): string {
  return `${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}-${Math.random().toString(36).slice(2, 7)}`;
}
