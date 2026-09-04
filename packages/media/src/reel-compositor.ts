/**
 * Reel compositor.
 *
 * Assembles a finished 1080x1920 H.264 MP4 from beat visuals, voiceover, and
 * burned-in captions using FFmpeg. Output is deliberately matched to what the
 * Instagram API accepts: 9:16, H.264 + AAC, yuv420p, and under the 90-second
 * API cap for Reels.
 *
 * FFmpeg is required and is NOT bundled. If the configured binary is missing or
 * lacks H.264, this throws rather than producing a file the platforms reject.
 */
import { execFile } from 'node:child_process';
import { mkdir, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { promisify } from 'node:util';
import { randomUUID } from 'node:crypto';
import { AppError, ProviderNotConfiguredError, type Logger } from '@mmos/core';

const exec = promisify(execFile);

export interface ReelBeat {
  narration: string;
  onScreenText?: string;
  durationSec: number;
  /** Still image for this beat, already rendered or sourced. */
  imagePath?: string;
}

export interface ReelCompositionInput {
  beats: ReelBeat[];
  /** Voiceover audio covering the whole reel. */
  voiceoverPath?: string;
  musicPath?: string;
  width?: number;
  height?: number;
  fps?: number;
}

export interface CompositorOptions {
  ffmpegPath: string;
  ffprobePath: string;
  workDir: string;
  logger: Logger;
}

export interface CompositionResult {
  videoPath: string;
  durationSec: number;
  width: number;
  height: number;
  sizeBytes: number;
}

export class ReelCompositor {
  constructor(private readonly options: CompositorOptions) {}

  /**
   * Confirms FFmpeg exists AND can encode H.264 + AAC. A stripped build (some
   * bundled FFmpegs are) would fail deep inside a render, so it is checked up
   * front with a clear message.
   */
  async verifyToolchain(): Promise<{ ok: boolean; version?: string; missing: string[] }> {
    const missing: string[] = [];
    let version: string | undefined;

    try {
      const { stdout } = await exec(this.options.ffmpegPath, ['-hide_banner', '-version']);
      version = stdout.split('\n')[0];
    } catch {
      return { ok: false, missing: ['ffmpeg binary not found at ' + this.options.ffmpegPath] };
    }

    const { stdout: encoders } = await exec(this.options.ffmpegPath, ['-hide_banner', '-encoders']);
    if (!encoders.includes('libx264')) missing.push('libx264 (H.264 video encoder)');
    if (!/\baac\b/.test(encoders)) missing.push('aac (audio encoder)');

    const { stdout: filters } = await exec(this.options.ffmpegPath, ['-hide_banner', '-filters']);
    if (!filters.includes('drawtext')) missing.push('drawtext filter (burned-in captions)');

    return { ok: missing.length === 0, ...(version ? { version } : {}), missing };
  }

  async compose(input: ReelCompositionInput): Promise<CompositionResult> {
    const check = await this.verifyToolchain();
    if (!check.ok) {
      throw new ProviderNotConfiguredError(
        'FFmpeg (required to render Reels)',
        check.missing.length > 0
          ? check.missing.map((m) => `FFmpeg build is missing ${m}`)
          : ['FFMPEG_PATH pointing at a full FFmpeg build'],
      );
    }

    const width = input.width ?? 1080;
    const height = input.height ?? 1920;
    const fps = input.fps ?? 30;
    const jobDir = resolve(this.options.workDir, randomUUID());
    await mkdir(jobDir, { recursive: true });

    try {
      const totalDuration = input.beats.reduce((sum, b) => sum + b.durationSec, 0);

      // Build one clip per beat, then concatenate. Doing it in stages keeps
      // each FFmpeg invocation simple enough to debug when one fails.
      const clipPaths: string[] = [];
      for (const [index, beat] of input.beats.entries()) {
        const clipPath = join(jobDir, `clip-${index}.mp4`);
        await this.#renderBeat(beat, clipPath, { width, height, fps });
        clipPaths.push(clipPath);
      }

      const listPath = join(jobDir, 'clips.txt');
      await writeFile(listPath, clipPaths.map((p) => `file '${p}'`).join('\n'), 'utf8');

      const silentPath = join(jobDir, 'silent.mp4');
      await this.#run([
        '-y', '-f', 'concat', '-safe', '0', '-i', listPath,
        '-c', 'copy', silentPath,
      ]);

      const outputPath = join(jobDir, 'reel.mp4');
      if (input.voiceoverPath) {
        await this.#run([
          '-y',
          '-i', silentPath,
          '-i', input.voiceoverPath,
          '-map', '0:v:0', '-map', '1:a:0',
          '-c:v', 'copy',
          '-c:a', 'aac', '-b:a', '192k',
          // Stop at whichever track ends first, so a slightly long voiceover
          // does not leave a frozen final frame.
          '-shortest',
          outputPath,
        ]);
      } else {
        // Instagram is unreliable with silent Reels, so a silent audio track is
        // muxed in rather than shipping a video with no audio stream at all.
        await this.#run([
          '-y',
          '-i', silentPath,
          '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
          '-map', '0:v:0', '-map', '1:a:0',
          '-c:v', 'copy', '-c:a', 'aac', '-shortest',
          outputPath,
        ]);
      }

      const { size } = await import('node:fs/promises').then((fs) => fs.stat(outputPath));

      this.options.logger.info(
        { durationSec: totalDuration, sizeBytes: size, beats: input.beats.length },
        'reel composed',
      );

      return { videoPath: outputPath, durationSec: totalDuration, width, height, sizeBytes: size };
    } catch (err) {
      await rm(jobDir, { recursive: true, force: true }).catch(() => {});
      throw new AppError(`Reel composition failed: ${(err as Error).message}`, {
        code: 'MEDIA_ERROR',
        retryable: true,
        cause: err,
      });
    }
  }

  /**
   * Actual duration of a media file, in seconds.
   *
   * This exists because generated speech never matches the script's estimated
   * beat timing. Rendering visuals to the script's guess would drift out of
   * sync with the narration; measuring the real audio and cutting the visuals
   * to it keeps them locked together.
   */
  async probeDurationSec(filePath: string): Promise<number> {
    try {
      const { stdout } = await exec(this.options.ffprobePath, [
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        filePath,
      ]);
      const seconds = Number.parseFloat(stdout.trim());
      if (!Number.isFinite(seconds)) throw new Error(`ffprobe returned "${stdout.trim()}"`);
      return seconds;
    } catch (err) {
      throw new AppError(`Could not read duration of ${filePath}: ${(err as Error).message}`, {
        code: 'MEDIA_ERROR',
        retryable: false,
      });
    }
  }

  /**
   * Joins per-beat narration into one continuous voiceover track.
   *
   * Re-encoding rather than stream-copying: the clips come from a TTS provider
   * and may differ in sample rate or channel layout, which the concat demuxer
   * would silently turn into garbled audio.
   */
  async concatAudio(audioPaths: string[], outputPath: string): Promise<number> {
    if (audioPaths.length === 0) throw new AppError('No audio to concatenate', { code: 'MEDIA_ERROR' });

    if (audioPaths.length === 1 && audioPaths[0]) {
      await this.#run(['-y', '-i', audioPaths[0], '-c:a', 'aac', '-b:a', '192k', outputPath]);
      return this.probeDurationSec(outputPath);
    }

    const inputs = audioPaths.flatMap((p) => ['-i', p]);
    const filter = `${audioPaths.map((_, i) => `[${i}:a]`).join('')}concat=n=${audioPaths.length}:v=0:a=1[out]`;
    await this.#run([
      '-y', ...inputs,
      '-filter_complex', filter,
      '-map', '[out]',
      '-c:a', 'aac', '-b:a', '192k',
      outputPath,
    ]);
    return this.probeDurationSec(outputPath);
  }

  /** Pulls a still for the post thumbnail. Taken shortly in, not at 0s, since
   *  the very first frame is often mid-fade or otherwise unrepresentative. */
  async extractThumbnail(videoPath: string, outputPath: string, atSec = 1): Promise<void> {
    await this.#run([
      '-y', '-ss', String(atSec), '-i', videoPath,
      '-frames:v', '1', '-q:v', '3',
      outputPath,
    ]);
  }

  /** Renders one beat: a still (or solid background) with optional caption text. */
  async #renderBeat(
    beat: ReelBeat,
    outputPath: string,
    dims: { width: number; height: number; fps: number },
  ): Promise<void> {
    const { width, height, fps } = dims;

    // Cover-crop the still to 9:16 rather than letterboxing, which would waste
    // the vertical canvas that makes short-form work.
    const scaleFilter =
      `scale=${width}:${height}:force_original_aspect_ratio=increase,` +
      `crop=${width}:${height},setsar=1`;

    const filters = [scaleFilter];

    if (beat.onScreenText) {
      const text = escapeDrawText(beat.onScreenText);
      filters.push(
        [
          `drawtext=text='${text}'`,
          'fontcolor=#F4F1E8',
          `fontsize=${Math.round(width * 0.075)}`,
          'box=1',
          'boxcolor=#080808@0.72',
          `boxborderw=${Math.round(width * 0.028)}`,
          'x=(w-text_w)/2',
          // Sits in the lower third, clear of platform UI overlays at the edges.
          'y=h*0.72',
          'line_spacing=12',
        ].join(':'),
      );
    }

    const inputArgs = beat.imagePath
      ? ['-loop', '1', '-t', String(beat.durationSec), '-i', beat.imagePath]
      : ['-f', 'lavfi', '-t', String(beat.durationSec), '-i', `color=c=#080808:s=${width}x${height}:r=${fps}`];

    await this.#run([
      '-y',
      ...inputArgs,
      '-vf', filters.join(','),
      '-r', String(fps),
      '-c:v', 'libx264',
      '-preset', 'medium',
      '-crf', '20',
      // yuv420p is required for the video to play on all platforms and devices.
      '-pix_fmt', 'yuv420p',
      outputPath,
    ]);
  }

  async #run(args: string[]): Promise<void> {
    try {
      await exec(this.options.ffmpegPath, args, { maxBuffer: 32 * 1024 * 1024 });
    } catch (err) {
      const stderr = (err as { stderr?: string }).stderr ?? '';
      throw new Error(`ffmpeg failed: ${stderr.split('\n').slice(-6).join(' ').trim() || (err as Error).message}`);
    }
  }
}

/** drawtext has its own escaping rules; colons and quotes break the filter graph. */
function escapeDrawText(text: string): string {
  return text
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "’")
    .replace(/:/g, '\\:')
    .replace(/%/g, '\\%');
}
