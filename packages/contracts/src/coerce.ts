/**
 * Lenient field types for model output.
 *
 * The problem these solve: a schema is an all-or-nothing gate. If a model
 * returns a 95-character headline against `max(90)`, Zod rejects the entire
 * object — all ten slides of the carousel — and the caller retries, pays again,
 * and very likely overruns again. A cosmetic overshoot should not destroy a
 * good generation.
 *
 * So the rule is: **coerce what is cosmetic, reject what is semantic.**
 *
 *   - Length limits on prose are cosmetic. Trim them.
 *   - Numeric ranges are cosmetic. Clamp them.
 *   - Enums, structure, and anything a safety or platform gate depends on are
 *     semantic. Those still reject, because a wrong value there is a real
 *     error and silently "fixing" it would hide a failure.
 *
 * Everything here runs before validation, so downstream code still receives
 * values that satisfy the documented bounds.
 */
import { z } from 'zod';

/**
 * Trims to `max` characters at a word boundary.
 *
 * Cutting mid-word looks like a bug to a reader, so a boundary is preferred —
 * but only when it retains most of the text. Otherwise an early space would
 * throw away nearly all of it, which is worse than a clean hard cut.
 */
export function trimToLength(text: string, max: number): string {
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;

  const cut = trimmed.slice(0, max);
  const lastSpace = cut.lastIndexOf(' ');
  return lastSpace > max * 0.7 ? cut.slice(0, lastSpace).trimEnd() : cut.trimEnd();
}

/** A string that is trimmed to length rather than rejected for overrunning. */
export function clampedString(max: number) {
  return z
    .string()
    .transform((value) => trimToLength(value, max))
    .pipe(z.string().max(max));
}

/** Optional variant, preserving absence rather than turning it into ''. */
export function clampedStringOptional(max: number) {
  return z
    .string()
    .transform((value) => trimToLength(value, max))
    .pipe(z.string().max(max))
    .optional();
}

/** A string with a default, for fields a model routinely omits entirely. */
export function clampedStringWithDefault(max: number, fallback = '') {
  return z
    .string()
    .optional()
    .transform((value) => trimToLength(value ?? fallback, max));
}

/** A number clamped into range rather than rejected for falling outside it. */
export function clampedNumber(min: number, max: number) {
  return z
    .number()
    .transform((value) => Math.min(max, Math.max(min, value)))
    .pipe(z.number().min(min).max(max));
}

/**
 * An array truncated to `max` rather than rejected for being too long.
 *
 * `min` is still enforced: too few items usually means the model misunderstood
 * the task, and there is nothing sensible to invent in its place.
 */
export function clampedArray<T extends z.ZodTypeAny>(
  item: T,
  { min, max }: { min?: number; max: number },
) {
  const base = z.array(item).transform((values) => values.slice(0, max));
  return min === undefined ? base : base.pipe(z.array(item).min(min));
}
