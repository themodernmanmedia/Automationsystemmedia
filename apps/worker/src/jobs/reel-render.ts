/**
 * Reel rendering.
 *
 * Turns a written Reel script into a finished, publishable MP4.
 *
 * The central problem this solves is synchronisation. A script's beat timings
 * are the writer's estimate; generated speech has its own real duration. If the
 * visuals were cut to the estimate, narration and captions would drift apart
 * over the length of the reel. So narration is synthesised per beat, each
 * clip's true duration is measured, and the visuals are cut to that instead.
 *
 * This job requires a voice provider and FFmpeg. Neither is faked: a missing
 * provider marks the reel FAILED with the reason rather than emitting a silent
 * or placeholder video.
 */
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { AppError, ProviderNotConfiguredError, type Logger } from '@mmos/core';
import { prisma } from '@mmos/db';
import type { ImageProvider, StorageProvider, VoiceProvider } from '@mmos/ai';
import { getCapabilities } from '@mmos/platforms';
import { ReelCompositor, type ReelBeat } from '@mmos/media';

/** Shape of the beats persisted on the Reel row by the writer agent. */
interface ScriptBeat {
  beat: string;
  narration: string;
  onScreenText?: string;
  visualDirection: string;
  durationSec: number;
}

export interface ReelRenderDeps {
  organizationId: string;
  voice: VoiceProvider | null;
  image: ImageProvider | null;
  storage: StorageProvider | null;
  compositor: ReelCompositor;
  logger: Logger;
  /** Records generation spend against the content piece. */
  recordCost?: (entry: {
    service: string;
    provider: string;
    operation: string;
    units?: number;
    costUsd: number;
    contentPieceId: string;
  }) => Promise<void>;
}

export interface ReelRenderResult {
  reelId: string;
  contentPieceId: string;
  videoUrl: string;
  durationSec: number;
  sizeBytes: number;
}

/**
 * Renders every reel waiting on the queue. Failures are isolated per reel — one
 * bad script must not stop the rest of the backlog from rendering.
 */
export async function renderPendingReels(
  deps: ReelRenderDeps,
  limit = 3,
): Promise<{ rendered: number; failed: number }> {
  const pending = await prisma.reel.findMany({
    where: {
      renderStatus: 'PENDING',
      contentPiece: {
        organizationId: deps.organizationId,
        // Only content that survived QA is worth spending render budget on.
        status: { in: ['APPROVED', 'SCHEDULED', 'QA'] },
      },
    },
    include: { contentPiece: { select: { id: true, title: true } } },
    orderBy: { createdAt: 'asc' },
    take: limit,
  });

  let rendered = 0;
  let failed = 0;

  for (const reel of pending) {
    try {
      const result = await renderReel(deps, reel.id);
      deps.logger.info(
        { reelId: result.reelId, durationSec: result.durationSec, sizeBytes: result.sizeBytes },
        'reel rendered',
      );
      rendered++;
    } catch (err) {
      failed++;
      const message = (err as Error).message;
      deps.logger.error({ err, reelId: reel.id }, 'reel render failed');
      await prisma.reel.update({
        where: { id: reel.id },
        data: { renderStatus: 'FAILED', renderError: message },
      });
      // A reel that cannot be rendered cannot be published, so it leaves the
      // automated path rather than sitting in the queue forever.
      await prisma.contentPiece.update({
        where: { id: reel.contentPieceId },
        data: {
          status: 'FLAGGED',
          flagReason: `Reel rendering failed: ${message}`,
          flaggedAt: new Date(),
        },
      });
    }
  }

  return { rendered, failed };
}

export async function renderReel(deps: ReelRenderDeps, reelId: string): Promise<ReelRenderResult> {
  if (!deps.voice) {
    throw new ProviderNotConfiguredError('Voice (required to render Reels)', [
      'VOICE_PROVIDER',
      'ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID, or OPENAI_API_KEY',
    ]);
  }
  if (!deps.storage) {
    throw new ProviderNotConfiguredError('Object storage (required to publish Reels)', [
      'S3_BUCKET',
      'S3_ACCESS_KEY_ID',
      'S3_SECRET_ACCESS_KEY',
      'S3_PUBLIC_BASE_URL',
    ]);
  }

  const reel = await prisma.reel.findUnique({
    where: { id: reelId },
    include: { contentPiece: { select: { id: true, title: true, organizationId: true } } },
  });
  if (!reel) throw new AppError(`Reel not found: ${reelId}`, { code: 'NOT_FOUND', httpStatus: 404 });

  const beats = reel.scriptBeats as unknown as ScriptBeat[];
  if (!Array.isArray(beats) || beats.length === 0) {
    throw new AppError(`Reel ${reelId} has no script beats`, { code: 'MEDIA_ERROR', retryable: false });
  }

  await prisma.reel.update({
    where: { id: reelId },
    data: { renderStatus: 'RENDERING', renderError: null },
  });

  const workDir = await mkdtemp(join(tmpdir(), 'mmos-reel-'));
  const log = deps.logger.child({ reelId, contentPieceId: reel.contentPieceId });

  try {
    /* ---- 1. narration per beat, measured rather than assumed ---- */

    const audioPaths: string[] = [];
    const timedBeats: ReelBeat[] = [];
    let voiceCost = 0;

    for (const [index, beat] of beats.entries()) {
      const audio = await deps.voice.synthesize({ text: beat.narration, format: 'mp3' });
      voiceCost += audio.costUsd;

      const audioPath = join(workDir, `narration-${index}.mp3`);
      await writeFile(audioPath, audio.data);
      audioPaths.push(audioPath);

      const spokenSec = await deps.compositor.probeDurationSec(audioPath);
      // A small tail so the next beat does not cut the last word, and so the
      // visual does not switch on the exact syllable the sentence ends.
      const beatDuration = Number((spokenSec + 0.35).toFixed(2));

      timedBeats.push({
        narration: beat.narration,
        ...(beat.onScreenText ? { onScreenText: beat.onScreenText } : {}),
        durationSec: beatDuration,
      });

      log.debug(
        { index, scriptedSec: beat.durationSec, spokenSec: Number(spokenSec.toFixed(2)) },
        'beat narration measured',
      );
    }

    /* ---- 2. platform duration ceiling, checked before rendering ---- */

    const totalSec = timedBeats.reduce((sum, b) => sum + b.durationSec, 0);
    const caps = getCapabilities('INSTAGRAM')?.video;
    const maxSec = caps?.maxDurationSec ?? 90;
    const minSec = caps?.minDurationSec ?? 5;

    if (totalSec > maxSec) {
      // Refuse rather than truncate: cutting the end of a reel removes the
      // payoff and the CTA, which is the whole reason the piece exists.
      throw new AppError(
        `Narrated reel runs ${totalSec.toFixed(1)}s but the Instagram API caps Reels at ${maxSec}s. Shorten the script and regenerate.`,
        { code: 'MEDIA_ERROR', retryable: false },
      );
    }
    if (totalSec < minSec) {
      throw new AppError(
        `Narrated reel runs only ${totalSec.toFixed(1)}s; Instagram requires at least ${minSec}s.`,
        { code: 'MEDIA_ERROR', retryable: false },
      );
    }

    /* ---- 3. beat visuals, when an image provider is configured ---- */

    let imageCost = 0;
    if (deps.image) {
      for (const [index, beat] of beats.entries()) {
        try {
          const [generated] = await deps.image.generate({
            prompt: buildVisualPrompt(beat.visualDirection),
            width: 1024,
            height: 1792,
          });
          if (!generated) continue;
          imageCost += generated.costUsd;

          const imagePath = join(workDir, `visual-${index}.png`);
          await writeFile(imagePath, generated.data);
          const target = timedBeats[index];
          if (target) target.imagePath = imagePath;
        } catch (err) {
          // A failed image is not a failed reel: the compositor falls back to
          // the brand background, which is a legitimate editorial look.
          log.warn({ err, index }, 'beat visual generation failed; using brand background');
        }
      }
    } else {
      log.info('no image provider configured; rendering on the brand background');
    }

    /* ---- 4. compose ---- */

    const voiceoverPath = join(workDir, 'voiceover.m4a');
    await deps.compositor.concatAudio(audioPaths, voiceoverPath);

    const composed = await deps.compositor.compose({ beats: timedBeats, voiceoverPath });

    const thumbnailPath = join(workDir, 'thumbnail.jpg');
    await deps.compositor.extractThumbnail(composed.videoPath, thumbnailPath, Math.min(1, totalSec / 2));

    /* ---- 5. upload; Meta fetches media from a public URL ---- */

    const { readFile } = await import('node:fs/promises');
    const videoBuffer = await readFile(composed.videoPath);
    const stored = await deps.storage.put(
      `reels/${reel.contentPieceId}/reel.mp4`,
      videoBuffer,
      'video/mp4',
    );

    const thumbBuffer = await readFile(thumbnailPath);
    const storedThumb = await deps.storage.put(
      `reels/${reel.contentPieceId}/thumbnail.jpg`,
      thumbBuffer,
      'image/jpeg',
    );

    const voiceBuffer = await readFile(voiceoverPath);
    const storedVoice = await deps.storage.put(
      `reels/${reel.contentPieceId}/voiceover.m4a`,
      voiceBuffer,
      'audio/mp4',
    );

    /* ---- 6. persist ---- */

    await prisma.reel.update({
      where: { id: reelId },
      data: {
        renderStatus: 'COMPLETE',
        renderError: null,
        renderedVideoUrl: stored.publicUrl,
        thumbnailUrl: storedThumb.publicUrl,
        durationSec: composed.durationSec,
        width: composed.width,
        height: composed.height,
      },
    });

    await prisma.audioAsset.create({
      data: {
        reelId,
        kind: 'voiceover',
        storageKey: storedVoice.key,
        publicUrl: storedVoice.publicUrl,
        mimeType: 'audio/mp4',
        durationSec: composed.durationSec,
        // Synthesised from our own script, so provenance is unambiguous.
        assetSource: 'GENERATED',
        rightsRisk: 'LOW',
        voiceProvider: deps.voice.name,
        transcript: timedBeats.map((b) => b.narration).join(' '),
      },
    });

    // The publisher reads MediaAsset rows, so the video must appear as one.
    await prisma.mediaAsset.create({
      data: {
        contentPieceId: reel.contentPieceId,
        kind: 'video',
        storageKey: stored.key,
        publicUrl: stored.publicUrl,
        mimeType: 'video/mp4',
        width: composed.width,
        height: composed.height,
        durationSec: composed.durationSec,
        fileSizeBytes: stored.sizeBytes,
        assetSource: 'GENERATED',
        rightsRisk: 'LOW',
      },
    });

    if (deps.recordCost && voiceCost + imageCost > 0) {
      await deps.recordCost({
        service: 'media',
        provider: deps.voice.name,
        operation: 'reel_render',
        units: composed.durationSec,
        costUsd: voiceCost + imageCost,
        contentPieceId: reel.contentPieceId,
      });
    }

    return {
      reelId,
      contentPieceId: reel.contentPieceId,
      videoUrl: stored.publicUrl,
      durationSec: composed.durationSec,
      sizeBytes: stored.sizeBytes,
    };
  } finally {
    await rm(workDir, { recursive: true, force: true }).catch(() => {});
  }
}

/** Keeps generated footage inside the brand's visual register. */
function buildVisualPrompt(visualDirection: string): string {
  return `${visualDirection}. Vertical 9:16 editorial photography for a premium men's business magazine. Dramatic directional lighting, deep shadows, muted desaturated palette with warm gold highlights. Cinematic, restrained, expensive. No text, no words, no logos, no watermarks, no faces looking at camera.`;
}
