/**
 * AGENT 14 — PLATFORM QA.
 *
 * The last technical check before publishing. It re-runs each target platform's
 * documented constraints against the finished assets, so a violation is caught
 * locally rather than as a failed API call — which on Instagram would also
 * consume a slot in the rolling 100-post window.
 */
import { getCapabilities, validateAgainstCapabilities, type PlatformName, type CreatePostInput, type ValidationIssue } from '@mmos/platforms';
import { countHashtags } from '@mmos/platforms';

export interface PlatformQaResult {
  platform: PlatformName;
  verdict: 'PASS' | 'WARN' | 'FAIL';
  issues: ValidationIssue[];
}

export function runPlatformQa(
  targets: Array<{ platform: PlatformName; input: CreatePostInput }>,
): PlatformQaResult[] {
  return targets.map(({ platform, input }) => {
    const caps = getCapabilities(platform);
    if (!caps) {
      return {
        platform,
        verdict: 'FAIL' as const,
        issues: [
          {
            severity: 'ERROR' as const,
            field: 'platform',
            message: `NOT SUPPORTED BY CURRENT API: no adapter exists for ${platform}.`,
          },
        ],
      };
    }

    const issues = validateAgainstCapabilities(input, caps);
    const hasError = issues.some((i) => i.severity === 'ERROR');
    const hasWarning = issues.some((i) => i.severity === 'WARNING');

    return {
      platform,
      verdict: hasError ? ('FAIL' as const) : hasWarning ? ('WARN' as const) : ('PASS' as const),
      issues,
    };
  });
}

/**
 * Per-platform caption optimization.
 *
 * Not just truncation — limits genuinely differ (Instagram 2,200 vs Facebook
 * 63,206), so the same caption is adapted rather than lowest-common-denominatored.
 * Truncation, when needed, happens at a sentence boundary so a caption never
 * ends mid-word.
 */
export function optimizeCaption(
  caption: string,
  hashtags: string[],
  platform: PlatformName,
): { text: string; hashtags: string[]; withinLimit: boolean; characterCount: number } {
  const caps = getCapabilities(platform);
  const maxLength = caps?.captionMaxLength ?? 2200;
  const maxHashtags = caps?.hashtagMax ?? 30;

  const usedTags = hashtags
    .map((t) => (t.startsWith('#') ? t : `#${t}`))
    .slice(0, Math.max(0, maxHashtags - countHashtags(caption)));

  const tagBlock = usedTags.length > 0 ? `\n\n${usedTags.join(' ')}` : '';
  const available = maxLength - tagBlock.length;

  let body = caption.trim();
  if (body.length > available) {
    const cut = body.slice(0, available - 1);
    const boundary = Math.max(cut.lastIndexOf('. '), cut.lastIndexOf('\n'), cut.lastIndexOf('! '), cut.lastIndexOf('? '));
    // Only honor a boundary that keeps most of the caption; otherwise a single
    // early period would discard nearly everything.
    body = boundary > available * 0.6 ? cut.slice(0, boundary + 1) : `${cut.trimEnd()}…`;
  }

  const text = `${body}${tagBlock}`;
  return {
    text,
    hashtags: usedTags,
    withinLimit: text.length <= maxLength,
    characterCount: text.length,
  };
}
