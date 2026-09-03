/**
 * Structural validation against a platform's documented constraints.
 *
 * Runs before publishing so a violation is caught locally rather than becoming
 * a failed API call. On Instagram that matters twice over: a rejected publish
 * still consumes attempts against a 100-post rolling window.
 */
import type { CreatePostInput, PlatformCapabilities, ValidationIssue } from './types.js';

export function validateAgainstCapabilities(
  input: CreatePostInput,
  caps: PlatformCapabilities,
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const err = (field: string, message: string) =>
    issues.push({ severity: 'ERROR', field, message });
  const warn = (field: string, message: string) =>
    issues.push({ severity: 'WARNING', field, message });

  /* ---- capability gates ---- */
  if (input.kind === 'CAROUSEL' && !caps.canPostCarousel) {
    err('kind', `NOT SUPPORTED BY CURRENT API: ${caps.displayName} cannot post carousels.`);
  }
  if ((input.kind === 'VIDEO' || input.kind === 'REEL') && !caps.canPostVideo) {
    err('kind', `NOT SUPPORTED BY CURRENT API: ${caps.displayName} cannot post video.`);
  }
  if (input.kind === 'IMAGE' && !caps.canPostImage) {
    err('kind', `NOT SUPPORTED BY CURRENT API: ${caps.displayName} cannot post single images.`);
  }
  if (input.kind === 'STORY' && !caps.canPostStory) {
    err('kind', `NOT SUPPORTED BY CURRENT API: ${caps.displayName} cannot post stories.`);
  }

  /* ---- caption ---- */
  if (input.caption.length > caps.captionMaxLength) {
    err(
      'caption',
      `Caption is ${input.caption.length} characters; ${caps.displayName} allows ${caps.captionMaxLength}.`,
    );
  }
  const hashtags = countHashtags(input.caption);
  if (hashtags > caps.hashtagMax) {
    err('caption', `Caption has ${hashtags} hashtags; ${caps.displayName} allows ${caps.hashtagMax}.`);
  }

  /* ---- media presence and count ---- */
  if (input.media.length === 0) {
    err('media', 'At least one media item is required.');
    return issues; // nothing further to validate
  }
  if (input.kind === 'CAROUSEL') {
    const min = caps.carouselMin ?? 2;
    const max = caps.carouselMax ?? 10;
    if (input.media.length < min || input.media.length > max) {
      err('media', `${caps.displayName} carousels need ${min}-${max} items; got ${input.media.length}.`);
    }
  }

  /* ---- per-item constraints ---- */
  for (const [i, item] of input.media.entries()) {
    const c = item.kind === 'VIDEO' ? caps.video : caps.image;
    const at = `media[${i}]`;

    if (!c.formats.includes(item.mimeType)) {
      err(at, `${item.mimeType} is not accepted by ${caps.displayName}. Allowed: ${c.formats.join(', ')}.`);
    }
    if (item.fileSizeBytes && item.fileSizeBytes > c.maxFileSizeBytes) {
      err(
        at,
        `File is ${mb(item.fileSizeBytes)}MB; ${caps.displayName} allows ${mb(c.maxFileSizeBytes)}MB.`,
      );
    }
    if (item.width && c.minWidth && item.width < c.minWidth) {
      err(at, `Width ${item.width}px is below the ${c.minWidth}px minimum.`);
    }
    if (item.width && c.maxWidth && item.width > c.maxWidth) {
      warn(at, `Width ${item.width}px exceeds ${c.maxWidth}px and will be downscaled by the platform.`);
    }
    if (item.kind === 'VIDEO' && item.durationSec !== undefined) {
      if (c.minDurationSec && item.durationSec < c.minDurationSec) {
        err(at, `Video is ${item.durationSec}s; ${caps.displayName} requires at least ${c.minDurationSec}s.`);
      }
      if (c.maxDurationSec && item.durationSec > c.maxDurationSec) {
        err(at, `Video is ${item.durationSec}s; ${caps.displayName} allows at most ${c.maxDurationSec}s.`);
      }
    }
    if (item.width && item.height && c.aspectRatioMin && c.aspectRatioMax) {
      const ratio = item.width / item.height;
      // Floating-point ratios never land exactly on 0.5625, so allow a small epsilon.
      if (ratio < c.aspectRatioMin - 0.01 || ratio > c.aspectRatioMax + 0.01) {
        err(
          at,
          `Aspect ratio ${ratio.toFixed(3)} is outside the accepted ${c.aspectRatioMin}-${c.aspectRatioMax} range.`,
        );
      }
    }
    if (caps.mediaDelivery === 'PULL_FROM_URL' && !isPubliclyFetchable(item.url)) {
      err(
        at,
        `${caps.displayName} fetches media from a public URL. "${item.url}" is not publicly resolvable — configure S3 storage.`,
      );
    }
  }

  /* ---- scheduling ---- */
  if (input.scheduledAt) {
    if (input.scheduledAt.getTime() <= Date.now()) {
      err('scheduledAt', 'Scheduled time is in the past.');
    }
    if (caps.scheduleStrategy === 'DELEGATED') {
      const minutesOut = (input.scheduledAt.getTime() - Date.now()) / 60_000;
      if (minutesOut < 10) {
        err('scheduledAt', `${caps.displayName} requires a scheduled time at least 10 minutes out.`);
      }
      if (minutesOut > 30 * 24 * 60) {
        err('scheduledAt', `${caps.displayName} allows scheduling at most 30 days out.`);
      }
    }
  }

  return issues;
}

export function countHashtags(text: string): number {
  return (text.match(/#[\p{L}\p{N}_]+/gu) ?? []).length;
}

function mb(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1);
}

/** Meta cannot fetch from localhost or a private address. Catch it before publishing. */
function isPubliclyFetchable(url: string): boolean {
  try {
    const u = new URL(url);
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return false;
    const host = u.hostname.toLowerCase();
    if (host === 'localhost' || host.endsWith('.local') || host.endsWith('.localhost')) return false;
    if (/^127\./.test(host) || host === '::1' || host === '0.0.0.0') return false;
    if (/^10\./.test(host) || /^192\.168\./.test(host)) return false;
    if (/^172\.(1[6-9]|2\d|3[01])\./.test(host)) return false;
    return true;
  } catch {
    return false;
  }
}

export function hasErrors(issues: ValidationIssue[]): boolean {
  return issues.some((i) => i.severity === 'ERROR');
}
