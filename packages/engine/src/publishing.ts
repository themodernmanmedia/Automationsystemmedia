/**
 * Publishing service.
 *
 * Owns the path from an approved content piece to a live post. Every guarantee
 * that matters is enforced here rather than in a worker:
 *   - the kill switch is re-checked immediately before the platform call
 *   - the content lifecycle forbids publishing from an unfinished state
 *   - every attempt, success or failure, is recorded with the raw response
 *   - errors are classified so retry is a decision, not a guess
 */
import { prisma, TokenStore, type PublishingJob } from '@mmos/db';
import {
  AppError,
  ForbiddenError,
  NotFoundError,
  PlatformAuthError,
  isRetryable,
  type Logger,
} from '@mmos/core';
import { AdapterRegistry, type CreatePostInput, type PlatformName, type PublishResult } from '@mmos/platforms';
import { isPublishable, type ContentStatus } from '@mmos/contracts';
import type { AutomationService } from './automation.js';
import { decideSchedule } from './scheduling.js';

export interface PublishServiceDeps {
  adapters: AdapterRegistry;
  tokens: TokenStore;
  automation: AutomationService;
  logger: Logger;
}

export class PublishingService {
  constructor(private readonly deps: PublishServiceDeps) {}

  /**
   * Creates one job per target account. `idempotencyKey` is a unique index in
   * the database, so a duplicated enqueue — a retried API call, a worker
   * restart mid-loop — cannot produce two posts of the same content.
   */
  async schedule(input: {
    organizationId: string;
    contentPieceId: string;
    socialAccountIds: string[];
    scheduledAt?: Date;
  }): Promise<PublishingJob[]> {
    const piece = await prisma.contentPiece.findFirst({
      where: { id: input.contentPieceId, organizationId: input.organizationId },
    });
    if (!piece) throw new NotFoundError('ContentPiece', input.contentPieceId);
    if (!isPublishable(piece.status as ContentStatus)) {
      throw new AppError(
        `Content piece is in status ${piece.status} and cannot be scheduled. It must reach APPROVED first.`,
        { code: 'VALIDATION_ERROR', httpStatus: 409 },
      );
    }

    const accounts = await prisma.socialAccount.findMany({
      where: { id: { in: input.socialAccountIds }, organizationId: input.organizationId },
    });

    const jobs: PublishingJob[] = [];
    for (const account of accounts) {
      const decision = decideSchedule(account.platform as PlatformName, input.scheduledAt);
      const scheduledAt = input.scheduledAt ?? new Date();
      const idempotencyKey = `${input.contentPieceId}:${account.id}:${scheduledAt.toISOString()}`;

      const job = await prisma.publishingJob.upsert({
        where: { idempotencyKey },
        create: {
          contentPieceId: input.contentPieceId,
          socialAccountId: account.id,
          platform: account.platform,
          status: input.scheduledAt ? 'SCHEDULED' : 'QUEUED',
          scheduledAt,
          scheduleStrategy: decision.strategy,
          idempotencyKey,
        },
        update: {}, // an existing job is left exactly as it is
      });
      jobs.push(job);
    }

    await prisma.contentPiece.update({
      where: { id: input.contentPieceId },
      data: { status: input.scheduledAt ? 'SCHEDULED' : 'APPROVED' },
    });
    await prisma.contentStatusChange.create({
      data: {
        contentPieceId: input.contentPieceId,
        fromStatus: piece.status,
        toStatus: input.scheduledAt ? 'SCHEDULED' : 'APPROVED',
        reason: `Scheduled to ${jobs.length} account(s)`,
      },
    });

    return jobs;
  }

  /** Executes one publishing job. Called by the worker. */
  async execute(jobId: string): Promise<PublishResult> {
    const job = await prisma.publishingJob.findUnique({
      where: { id: jobId },
      include: {
        socialAccount: true,
        contentPiece: {
          include: { carousel: { include: { slides: true } }, reel: true, captions: true, mediaAssets: true },
        },
      },
    });
    if (!job) throw new NotFoundError('PublishingJob', jobId);
    if (job.status === 'PUBLISHED') {
      throw new AppError('Job already published', { code: 'CONFLICT', httpStatus: 409 });
    }
    if (job.status === 'CANCELLED') throw new ForbiddenError('Job was cancelled');

    const { socialAccount: account, contentPiece: piece } = job;

    // The last stop check, immediately before we touch a platform. A job may
    // have been queued for hours; pausing must stop what is already in flight.
    await this.deps.automation.assertMayPublish(account.organizationId);

    if (!isPublishable(piece.status as ContentStatus)) {
      throw new ForbiddenError(
        `Content piece is in status ${piece.status}; refusing to publish unapproved content.`,
      );
    }

    await prisma.publishingJob.update({
      where: { id: jobId },
      data: { status: 'PUBLISHING', attemptCount: { increment: 1 } },
    });
    await prisma.contentPiece.update({ where: { id: piece.id }, data: { status: 'PUBLISHING' } });

    const attemptNumber = job.attemptCount + 1;
    const started = Date.now();

    try {
      const token = await this.deps.tokens.get(account.id);
      if (!token) {
        throw new PlatformAuthError(
          account.platform,
          `No stored credentials for ${account.username}. Reconnect the account.`,
        );
      }

      const adapter = this.deps.adapters.get(account.platform as PlatformName);
      const input = await this.#buildPostInput(job.id, piece, account.platform as PlatformName, job.scheduledAt, job.scheduleStrategy);

      const result = await adapter.createPost(
        { accessToken: token.accessToken, platformAccountId: account.platformAccountId, isAudited: account.isAudited },
        input,
      );

      await prisma.publishingAttempt.create({
        data: {
          publishingJobId: jobId,
          attemptNumber,
          step: 'publish',
          success: true,
          durationMs: Date.now() - started,
          responseBody: safeJson(result.raw),
        },
      });

      await prisma.publishingJob.update({
        where: { id: jobId },
        data: {
          status: 'PUBLISHED',
          platformPostId: result.platformPostId,
          platformUrl: result.platformUrl ?? null,
          publishedAt: result.publishedAt,
          lastError: null,
          lastErrorCode: null,
        },
      });

      await prisma.contentPiece.update({ where: { id: piece.id }, data: { status: 'PUBLISHED' } });
      await prisma.contentStatusChange.create({
        data: {
          contentPieceId: piece.id,
          fromStatus: 'PUBLISHING',
          toStatus: 'PUBLISHED',
          reason: `Published to ${account.platform} as ${result.platformPostId}`,
        },
      });
      await prisma.socialAccount.update({
        where: { id: account.id },
        data: { lastPublishAt: new Date(), lastPublishError: null },
      });
      await prisma.auditLog.create({
        data: {
          organizationId: account.organizationId,
          actorType: 'system',
          action: 'publish',
          subjectType: 'content_piece',
          subjectId: piece.id,
          diff: {
            platform: account.platform,
            platformPostId: result.platformPostId,
            restrictedVisibility: result.restrictedVisibility ?? false,
          },
        },
      });

      if (result.restrictedVisibility) {
        this.deps.logger.warn(
          { jobId, platform: account.platform, note: result.visibilityNote },
          'published with restricted visibility',
        );
      }

      return result;
    } catch (err) {
      const appErr = err instanceof AppError ? err : null;
      const retryable = isRetryable(err);

      await prisma.publishingAttempt.create({
        data: {
          publishingJobId: jobId,
          attemptNumber,
          step: 'publish',
          success: false,
          errorCode: appErr?.code ?? 'INTERNAL',
          errorMessage: (err as Error).message,
          httpStatus: appErr?.httpStatus ?? null,
          durationMs: Date.now() - started,
          responseBody: safeJson(appErr?.context),
        },
      });

      await prisma.publishingJob.update({
        where: { id: jobId },
        // A retryable failure returns to SCHEDULED so the worker picks it up
        // again; a permanent one goes to FAILED and stops consuming retries.
        data: {
          status: retryable ? 'SCHEDULED' : 'FAILED',
          lastError: (err as Error).message,
          lastErrorCode: appErr?.code ?? 'INTERNAL',
        },
      });

      if (!retryable) {
        await prisma.contentPiece.update({ where: { id: piece.id }, data: { status: 'FAILED' } });
      }

      // An auth failure means the account needs human attention, not a retry.
      if (err instanceof PlatformAuthError) {
        await prisma.socialAccount.update({
          where: { id: account.id },
          data: { status: 'TOKEN_EXPIRED', lastPublishError: (err as Error).message },
        });
      }

      throw err;
    }
  }

  /**
   * Assembles the platform-specific request from stored content. Caption is
   * chosen per platform because limits genuinely differ.
   */
  async #buildPostInput(
    jobId: string,
    piece: {
      id: string;
      format: string;
      hook: string;
      carousel: { slides: Array<{ position: number; renderedImageUrl: string | null }> } | null;
      reel: { renderedVideoUrl: string | null; durationSec: number | null } | null;
      captions: Array<{ platform: string; text: string }>;
      mediaAssets: Array<{ publicUrl: string; mimeType: string; width: number | null; height: number | null; durationSec: number | null; fileSizeBytes: number | null; kind: string }>;
    },
    platform: PlatformName,
    scheduledAt: Date,
    strategy: string,
  ): Promise<CreatePostInput> {
    const caption =
      piece.captions.find((c) => c.platform === platform)?.text ??
      piece.captions[0]?.text ??
      piece.hook;

    // Only a DELEGATED job carries a future timestamp to the platform. A
    // SELF_TIMED job is being fired *now*, at its scheduled moment, so passing
    // the time would make the adapter reject it as unsupported scheduling.
    const scheduleField = strategy === 'DELEGATED' ? { scheduledAt } : {};

    if (piece.format === 'CAROUSEL') {
      const slides = (piece.carousel?.slides ?? [])
        .slice()
        .sort((a, b) => a.position - b.position)
        .filter((s) => s.renderedImageUrl);
      if (slides.length === 0) {
        throw new AppError(`Carousel for job ${jobId} has no rendered slide images.`, {
          code: 'MEDIA_ERROR',
          retryable: false,
        });
      }
      return {
        kind: 'CAROUSEL',
        caption,
        media: slides.map((s) => ({
          url: s.renderedImageUrl as string,
          kind: 'IMAGE' as const,
          mimeType: 'image/jpeg',
          width: 1080,
          height: 1350,
        })),
        ...scheduleField,
      };
    }

    if (piece.format === 'REEL') {
      const url = piece.reel?.renderedVideoUrl;
      if (!url) {
        throw new AppError(`Reel for job ${jobId} has not been rendered.`, {
          code: 'MEDIA_ERROR',
          retryable: false,
        });
      }
      return {
        kind: 'REEL',
        caption,
        media: [
          {
            url,
            kind: 'VIDEO',
            mimeType: 'video/mp4',
            width: 1080,
            height: 1920,
            ...(piece.reel?.durationSec ? { durationSec: piece.reel.durationSec } : {}),
          },
        ],
        ...scheduleField,
      };
    }

    const image = piece.mediaAssets.find((a) => a.kind === 'image');
    if (!image) {
      throw new AppError(`Content piece ${piece.id} has no publishable media.`, {
        code: 'MEDIA_ERROR',
        retryable: false,
      });
    }
    return {
      kind: 'IMAGE',
      caption,
      media: [
        {
          url: image.publicUrl,
          kind: 'IMAGE',
          mimeType: image.mimeType,
          ...(image.width ? { width: image.width } : {}),
          ...(image.height ? { height: image.height } : {}),
          ...(image.fileSizeBytes ? { fileSizeBytes: image.fileSizeBytes } : {}),
        },
      ],
      ...scheduleField,
    };
  }

  /** Emergency control: clears everything not yet published. */
  async clearQueue(organizationId: string, actor: string): Promise<number> {
    const result = await prisma.publishingJob.updateMany({
      where: {
        socialAccount: { organizationId },
        status: { in: ['QUEUED', 'SCHEDULED'] },
      },
      data: { status: 'CANCELLED', blockedReason: `Queue cleared by ${actor}` },
    });
    await prisma.auditLog.create({
      data: {
        organizationId,
        actorType: 'user',
        actorId: actor,
        action: 'clear_queue',
        diff: { cancelledJobs: result.count },
      },
    });
    return result.count;
  }
}

/** Prisma's Json column rejects undefined and cyclic values. */
function safeJson(value: unknown): object | undefined {
  if (value === undefined || value === null) return undefined;
  try {
    return JSON.parse(JSON.stringify(value)) as object;
  } catch {
    return { unserializable: true };
  }
}
