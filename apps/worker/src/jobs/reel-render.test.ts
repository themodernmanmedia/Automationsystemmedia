/**
 * Reel render job — integration test against real Postgres and real FFmpeg.
 *
 * The behaviour that matters here is synchronisation: visuals must be cut to
 * the ACTUAL duration of generated speech, not to the script's estimate. So the
 * fake voice provider deliberately returns audio whose length disagrees with
 * the script, and the test asserts the finished video follows the audio.
 */
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createLogger, ProviderNotConfiguredError } from '@mmos/core';
import { prisma } from '@mmos/db';
import { ReelCompositor } from '@mmos/media';
import type { GeneratedAudio, StorageProvider, StoredObject, VoiceProvider } from '@mmos/ai';
import { renderPendingReels, renderReel } from './reel-render.js';

const exec = promisify(execFile);
const logger = createLogger({ level: 'silent' });
const FFMPEG = process.env['FFMPEG_PATH'] ?? '/usr/bin/ffmpeg';
const FFPROBE = process.env['FFPROBE_PATH'] ?? '/usr/bin/ffprobe';

let workDir: string;
let organizationId: string;

/**
 * Synthesises a real 2-second tone per call. Two seconds regardless of text,
 * while the script claims 5s per beat — so any code trusting the script's
 * timing instead of the audio will produce a visibly wrong duration.
 */
const SPOKEN_SEC = 2;
class FakeVoiceProvider implements VoiceProvider {
  readonly name = 'fake-voice';
  calls = 0;

  async synthesize(): Promise<GeneratedAudio> {
    this.calls++;
    const path = join(workDir, `tone-${this.calls}.mp3`);
    await exec(FFMPEG, [
      '-y', '-f', 'lavfi', '-i', `sine=frequency=200:duration=${SPOKEN_SEC}`,
      '-c:a', 'libmp3lame', path,
    ]);
    return { data: await readFile(path), mimeType: 'audio/mpeg', model: 'fake', costUsd: 0.01 };
  }
}

/** Captures uploads so the test can assert what would reach the platforms. */
class MemoryStorage implements StorageProvider {
  readonly name = 'memory';
  readonly objects = new Map<string, { size: number; mimeType: string }>();

  async put(key: string, data: Buffer, mimeType: string): Promise<StoredObject> {
    this.objects.set(key, { size: data.byteLength, mimeType });
    return { key, publicUrl: this.getPublicUrl(key), sizeBytes: data.byteLength, mimeType };
  }
  getPublicUrl(key: string): string {
    return `https://cdn.example.com/${key}`;
  }
  async delete(key: string): Promise<void> {
    this.objects.delete(key);
  }
}

const compositor = new ReelCompositor({
  ffmpegPath: FFMPEG,
  ffprobePath: FFPROBE,
  workDir: '',
  logger,
});

/** Creates an approved REEL content piece with a script whose timings are wrong. */
async function seedReel(beatCount = 3, scriptedSecPerBeat = 5) {
  const piece = await prisma.contentPiece.create({
    data: {
      organizationId,
      format: 'REEL',
      status: 'APPROVED',
      category: 'BUSINESS',
      title: 'Test reel',
      hook: 'A test hook',
    },
  });
  const reel = await prisma.reel.create({
    data: {
      contentPieceId: piece.id,
      renderStatus: 'PENDING',
      voiceoverText: 'narration',
      scriptBeats: Array.from({ length: beatCount }, (_, i) => ({
        beat: i === 0 ? 'HOOK' : 'BODY',
        narration: `Narration for beat ${i}.`,
        onScreenText: `Beat ${i}`,
        visualDirection: 'A dark boardroom',
        durationSec: scriptedSecPerBeat,
      })),
    },
  });
  return { piece, reel };
}

beforeAll(async () => {
  workDir = await mkdtemp(join(tmpdir(), 'mmos-reel-test-'));
  const org = await prisma.organization.create({
    data: { name: 'Reel Test Org', slug: `reel-test-${Date.now()}` },
  });
  organizationId = org.id;
});

afterAll(async () => {
  // Cascades remove every content piece, reel, and asset this suite created,
  // so nothing is left behind for the next suite.
  await prisma.organization.deleteMany({ where: { id: organizationId } });
  await rm(workDir, { recursive: true, force: true });
  await prisma.$disconnect();
});

describe('renderReel', () => {
  it('cuts the video to the real narration length, not the script estimate', async () => {
    const voice = new FakeVoiceProvider();
    const storage = new MemoryStorage();
    const { reel } = await seedReel(3, 5); // script claims 15s; speech is ~6s

    const result = await renderReel(
      { organizationId, voice, image: null, storage, compositor, logger },
      reel.id,
    );

    // 3 beats x 2s of speech + 0.35s tail each = ~7.05s, nowhere near 15s.
    expect(result.durationSec).toBeGreaterThan(6);
    expect(result.durationSec).toBeLessThan(9);
    expect(voice.calls).toBe(3);

    const row = await prisma.reel.findUnique({ where: { id: reel.id } });
    expect(row!.renderStatus).toBe('COMPLETE');
    expect(row!.renderedVideoUrl).toBe(result.videoUrl);
    expect(row!.thumbnailUrl).toBeTruthy();
  }, 180_000);

  it('uploads a video, a thumbnail, and the voiceover', async () => {
    const storage = new MemoryStorage();
    // Three beats, so the reel clears Instagram's 5s minimum.
    const { reel } = await seedReel(3);

    await renderReel(
      { organizationId, voice: new FakeVoiceProvider(), image: null, storage, compositor, logger },
      reel.id,
    );

    const keys = [...storage.objects.keys()];
    expect(keys.some((k) => k.endsWith('reel.mp4'))).toBe(true);
    expect(keys.some((k) => k.endsWith('thumbnail.jpg'))).toBe(true);
    expect(keys.some((k) => k.endsWith('voiceover.m4a'))).toBe(true);
  }, 180_000);

  it('records the video as a MediaAsset so the publisher can find it', async () => {
    const { piece, reel } = await seedReel(3);

    await renderReel(
      { organizationId, voice: new FakeVoiceProvider(), image: null, storage: new MemoryStorage(), compositor, logger },
      reel.id,
    );

    const assets = await prisma.mediaAsset.findMany({ where: { contentPieceId: piece.id } });
    expect(assets).toHaveLength(1);
    expect(assets[0]!.kind).toBe('video');
    expect(assets[0]!.mimeType).toBe('video/mp4');
    expect(assets[0]!.width).toBe(1080);
    expect(assets[0]!.height).toBe(1920);
    // Generated from our own script, so it must clear the rights gate.
    expect(assets[0]!.assetSource).toBe('GENERATED');
    expect(assets[0]!.rightsRisk).toBe('LOW');

    const audio = await prisma.audioAsset.findMany({ where: { reelId: reel.id } });
    expect(audio[0]!.kind).toBe('voiceover');
    expect(audio[0]!.transcript).toContain('Narration for beat 0');
  }, 180_000);

  it('refuses when the narrated reel would exceed the Instagram 90s cap', async () => {
    // 50 beats x ~2.35s lands well past the API ceiling.
    const { reel } = await seedReel(50, 1);

    await expect(
      renderReel(
        { organizationId, voice: new FakeVoiceProvider(), image: null, storage: new MemoryStorage(), compositor, logger },
        reel.id,
      ),
    ).rejects.toThrow(/caps Reels at 90s/);
  }, 300_000);

  it('refuses without a voice provider rather than emitting a silent video', async () => {
    const { reel } = await seedReel(2);
    await expect(
      renderReel(
        { organizationId, voice: null, image: null, storage: new MemoryStorage(), compositor, logger },
        reel.id,
      ),
    ).rejects.toBeInstanceOf(ProviderNotConfiguredError);
  });

  it('refuses without storage, since Meta fetches media from a public URL', async () => {
    const { reel } = await seedReel(2);
    await expect(
      renderReel(
        { organizationId, voice: new FakeVoiceProvider(), image: null, storage: null, compositor, logger },
        reel.id,
      ),
    ).rejects.toBeInstanceOf(ProviderNotConfiguredError);
  });
});

describe('renderPendingReels', () => {
  it('flags the content piece when a render fails, so it leaves the automated path', async () => {
    const { piece, reel } = await seedReel(2);
    // No voice provider: every render in this pass fails.
    const result = await renderPendingReels({
      organizationId, voice: null, image: null, storage: new MemoryStorage(), compositor, logger,
    });

    expect(result.failed).toBeGreaterThanOrEqual(1);

    const reelRow = await prisma.reel.findUnique({ where: { id: reel.id } });
    expect(reelRow!.renderStatus).toBe('FAILED');
    expect(reelRow!.renderError).toMatch(/Voice/i);

    const pieceRow = await prisma.contentPiece.findUnique({ where: { id: piece.id } });
    expect(pieceRow!.status).toBe('FLAGGED');
    expect(pieceRow!.flagReason).toMatch(/Reel rendering failed/);
  }, 60_000);

  it('produces a genuinely publishable MP4 for a queued reel', async () => {
    // Clear anything left PENDING by earlier cases so this pass is deterministic.
    await prisma.reel.updateMany({
      where: { contentPiece: { organizationId }, renderStatus: 'PENDING' },
      data: { renderStatus: 'FAILED', renderError: 'skipped by test setup' },
    });

    const { reel } = await seedReel(3);
    const storage = new MemoryStorage();

    const result = await renderPendingReels({
      organizationId, voice: new FakeVoiceProvider(), image: null, storage, compositor, logger,
    });
    expect(result.rendered).toBe(1);
    expect(result.failed).toBe(0);

    const row = await prisma.reel.findUnique({ where: { id: reel.id } });
    expect(row!.renderStatus).toBe('COMPLETE');
    // Inside Instagram's 5-90s window for API-published Reels.
    expect(row!.durationSec!).toBeGreaterThanOrEqual(5);
    expect(row!.durationSec!).toBeLessThanOrEqual(90);
  }, 180_000);
});
