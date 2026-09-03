/**
 * Duplicate and near-duplicate detection.
 *
 * Runs without an embeddings API on purpose. Character trigram cosine
 * similarity catches the cases that actually occur here — the same story from
 * three outlets, or a hook rephrased — and it is deterministic, instant, and
 * free. An embedding provider can be layered on later behind the same
 * interface; the `embedding` column already exists for that.
 */
import { fingerprint } from '@mmos/core';

const TRIGRAM_SIZE = 3;

export function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function trigrams(text: string): Map<string, number> {
  const normalized = normalizeText(text);
  const counts = new Map<string, number>();
  if (normalized.length < TRIGRAM_SIZE) {
    if (normalized) counts.set(normalized, 1);
    return counts;
  }
  for (let i = 0; i <= normalized.length - TRIGRAM_SIZE; i++) {
    const gram = normalized.slice(i, i + TRIGRAM_SIZE);
    counts.set(gram, (counts.get(gram) ?? 0) + 1);
  }
  return counts;
}

/** Cosine similarity over trigram frequency vectors. Returns 0..1. */
export function similarity(a: string, b: string): number {
  const va = trigrams(a);
  const vb = trigrams(b);
  if (va.size === 0 || vb.size === 0) return 0;

  // Iterate the smaller map — only shared keys contribute to the dot product.
  const [small, large] = va.size <= vb.size ? [va, vb] : [vb, va];
  let dot = 0;
  for (const [gram, count] of small) {
    const other = large.get(gram);
    if (other) dot += count * other;
  }
  if (dot === 0) return 0;

  const magA = Math.sqrt([...va.values()].reduce((s, v) => s + v * v, 0));
  const magB = Math.sqrt([...vb.values()].reduce((s, v) => s + v * v, 0));
  return Number((dot / (magA * magB)).toFixed(4));
}

/** Exact-match key for cheap database-level dedupe before any similarity work. */
export function contentHash(text: string): string {
  return fingerprint(normalizeText(text));
}

export interface DuplicateCandidate {
  id: string;
  text: string;
}

export interface DuplicateMatch {
  id: string;
  similarity: number;
}

/**
 * Thresholds are tuned so that the same news story from different outlets is
 * caught, while two genuinely different takes on one subject are not. Topics
 * use a lower bar than hooks: near-identical topics waste research budget,
 * whereas hooks legitimately share phrasing patterns.
 */
export const SIMILARITY_THRESHOLDS = {
  topic: 0.72,
  hook: 0.85,
  script: 0.8,
  caption: 0.8,
} as const;

export function findDuplicates(
  text: string,
  candidates: DuplicateCandidate[],
  threshold: number = SIMILARITY_THRESHOLDS.topic,
): DuplicateMatch[] {
  return candidates
    .map((c) => ({ id: c.id, similarity: similarity(text, c.text) }))
    .filter((m) => m.similarity >= threshold)
    .sort((a, b) => b.similarity - a.similarity);
}

export function isDuplicate(
  text: string,
  candidates: DuplicateCandidate[],
  threshold: number = SIMILARITY_THRESHOLDS.topic,
): boolean {
  return findDuplicates(text, candidates, threshold).length > 0;
}
