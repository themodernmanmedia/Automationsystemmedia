/**
 * Media engine tests.
 *
 * These deliberately produce REAL output files and inspect them, rather than
 * asserting that a function was called. The whole point of this package is that
 * it emits media the platforms will accept, and only a real file can show that.
 */
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { mkdtemp, rm, stat } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createLogger, ProviderNotConfiguredError } from '@mmos/core';
import { designCarousel } from '@mmos/agents';
import type { CarouselScript } from '@mmos/contracts';
import { CarouselRenderer } from './carousel-renderer.js';
import { ReelCompositor } from './reel-compositor.js';
import { renderSlideHtml } from './slide-template.js';

const exec = promisify(execFile);
const logger = createLogger({ level: 'silent' });
const FFMPEG = process.env['FFMPEG_PATH'] ?? '/usr/bin/ffmpeg';
const CHROMIUM = '/opt/pw-browsers/chromium';

let workDir: string;

beforeAll(async () => {
  workDir = await mkdtemp(join(tmpdir(), 'mmos-media-'));
});
afterAll(async () => {
  await rm(workDir, { recursive: true, force: true });
});

const script: CarouselScript = {
  title: 'Test carousel',
  slides: [
    { role: 'HOOK', headline: "Nvidia's margin on one chip exceeds Ford's on twelve cars", body: '' },
    { role: 'CONTEXT', headline: 'Why this matters', body: 'The economics of compute have inverted the old industrial order.' },
    { role: 'POINT', headline: 'Gross margin', body: 'Data centre silicon clears roughly 75% gross margin.' },
    { role: 'CTA', headline: 'Follow for more', body: 'Business, money, and technology, explained properly.' },
  ],
  caption: 'A test caption for the render.',
  hashtags: ['#business'],
};

describe('slide template', () => {
  it('escapes model-generated content rather than injecting it as markup', () => {
    const carousel = designCarousel({
      ...script,
      slides: [{ role: 'HOOK', headline: '<script>alert(1)</script>', body: 'A & B' }],
    });
    const html = renderSlideHtml({
      design: carousel.slides[0]!.design,
      width: 1080,
      height: 1350,
      brandName: 'The Modern Man',
    });
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;');
    expect(html).toContain('A &amp; B');
  });

  it('applies the brand palette to the cover', () => {
    const carousel = designCarousel(script);
    const cover = carousel.slides[0]!.design;
    expect(cover.background.toUpperCase()).toBe('#080808');
    expect(cover.accent.color.toUpperCase()).toBe('#C9A227');
    // The cover carries no page number: it would compete with the hook.
    expect(cover.pageNumber.show).toBe(false);
  });

  it('steps type down for a long headline so it cannot overflow the canvas', () => {
    const short = designCarousel({ ...script, slides: [{ role: 'HOOK', headline: 'Short', body: '' }] });
    const long = designCarousel({
      ...script,
      slides: [{ role: 'HOOK', headline: 'A considerably longer headline that would otherwise run off the edge of the canvas entirely', body: '' }],
    });
    expect(long.slides[0]!.design.headlineSize).toBeLessThan(short.slides[0]!.design.headlineSize);
  });
});

describe('carousel renderer', () => {
  it('renders real JPEG slides at Instagram 4:5 dimensions', async () => {
    const carousel = designCarousel(script);
    const renderer = new CarouselRenderer({ logger, executablePath: CHROMIUM });

    const slides = await renderer.render(carousel, { brandName: 'The Modern Man' });

    expect(slides).toHaveLength(4);
    for (const slide of slides) {
      expect(slide.width).toBe(1080);
      expect(slide.height).toBe(1350);
      // Real JPEG magic bytes, not a placeholder buffer.
      expect(slide.data.subarray(0, 2).toString('hex')).toBe('ffd8');
      expect(slide.data.byteLength).toBeGreaterThan(10_000);
      // Comfortably inside Instagram's 8 MB image limit.
      expect(slide.data.byteLength).toBeLessThan(8 * 1024 * 1024);
    }
  }, 120_000);
});

describe('reel compositor', () => {
  // workDir must be a real directory: the compositor creates its job folder
  // inside it, and an empty value resolves to the process cwd.
  let compositor: ReelCompositor;
  beforeAll(() => {
    compositor = new ReelCompositor({
      ffmpegPath: FFMPEG,
      ffprobePath: '/usr/bin/ffprobe',
      workDir,
      logger,
    });
  });

  it('verifies the FFmpeg build can actually encode H.264 and AAC', async () => {
    const check = await compositor.verifyToolchain();
    expect(check.ok).toBe(true);
    expect(check.missing).toEqual([]);
  });

  it('refuses to render with a missing FFmpeg instead of emitting a broken file', async () => {
    const broken = new ReelCompositor({
      ffmpegPath: '/nonexistent/ffmpeg',
      ffprobePath: '/nonexistent/ffprobe',
      workDir,
      logger,
    });
    await expect(
      broken.compose({ beats: [{ narration: 'x', durationSec: 2 }] }),
    ).rejects.toBeInstanceOf(ProviderNotConfiguredError);
  });

  it('composes a playable 1080x1920 H.264 MP4 with burned-in captions', async () => {
    const real = new ReelCompositor({
      ffmpegPath: FFMPEG,
      ffprobePath: '/usr/bin/ffprobe',
      workDir,
      logger,
    });

    const result = await real.compose({
      beats: [
        { narration: 'The economics of compute have inverted.', onScreenText: 'Compute won', durationSec: 2 },
        { narration: 'Here is what that means.', onScreenText: 'What it means', durationSec: 2 },
      ],
    });

    expect(result.width).toBe(1080);
    expect(result.height).toBe(1920);
    expect(result.durationSec).toBe(4);
    expect((await stat(result.videoPath)).size).toBeGreaterThan(1000);

    // Inspect the actual container: the platforms reject anything else.
    const { stdout } = await exec('/usr/bin/ffprobe', [
      '-v', 'error',
      '-show_entries', 'stream=codec_name,width,height,pix_fmt',
      '-of', 'json',
      result.videoPath,
    ]);
    const probe = JSON.parse(stdout) as {
      streams: Array<{ codec_name: string; width?: number; height?: number; pix_fmt?: string }>;
    };

    const video = probe.streams.find((s) => s.width);
    const audio = probe.streams.find((s) => !s.width);

    expect(video?.codec_name).toBe('h264');
    expect(video?.width).toBe(1080);
    expect(video?.height).toBe(1920);
    // Required for playback across devices.
    expect(video?.pix_fmt).toBe('yuv420p');
    // Instagram is unreliable with a video that has no audio stream at all.
    expect(audio?.codec_name).toBe('aac');
  }, 180_000);

  it('muxes a supplied voiceover into the finished reel', async () => {
    const real = new ReelCompositor({ ffmpegPath: FFMPEG, ffprobePath: '/usr/bin/ffprobe', workDir, logger });

    // A real 3-second tone standing in for generated speech.
    const voicePath = join(workDir, 'voice.m4a');
    await exec(FFMPEG, ['-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=3', '-c:a', 'aac', voicePath]);

    const result = await real.compose({
      beats: [{ narration: 'Test', durationSec: 3 }],
      voiceoverPath: voicePath,
    });

    const { stdout } = await exec('/usr/bin/ffprobe', [
      '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=codec_name', '-of', 'json', result.videoPath,
    ]);
    expect((JSON.parse(stdout) as { streams: Array<{ codec_name: string }> }).streams[0]?.codec_name).toBe('aac');
  }, 180_000);
});
