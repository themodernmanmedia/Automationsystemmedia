/**
 * Provider-agnostic AI interfaces.
 *
 * The brief requires that no provider be load-bearing. Every agent depends on
 * these interfaces, never on a vendor SDK, so swapping Anthropic for OpenAI (or
 * adding a third) is a construction-site change, not a rewrite.
 */
import type { z } from 'zod';

export interface LlmMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface LlmRequest {
  system?: string;
  messages: LlmMessage[];
  maxTokens?: number;
  temperature?: number;
  model?: string;
  /** Attribution for the cost meter. */
  purpose?: string;
}

export interface LlmUsage {
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
}

export interface LlmResponse {
  text: string;
  model: string;
  usage: LlmUsage;
  stopReason?: string;
}

export interface LlmProvider {
  readonly name: string;
  readonly defaultModel: string;
  complete(request: LlmRequest): Promise<LlmResponse>;
  /**
   * Completion constrained to a Zod schema. Implementations must actually
   * validate the parsed result — a schema that is only advisory is worthless
   * for a pipeline that runs unattended.
   */
  completeStructured<T>(request: LlmRequest, schema: z.ZodType<T>, schemaName: string): Promise<{
    data: T;
    usage: LlmUsage;
    model: string;
  }>;
  estimateCost(inputTokens: number, outputTokens: number, model?: string): number;
}

/* ------------------------------ media ------------------------------ */

export interface ImageRequest {
  prompt: string;
  width?: number;
  height?: number;
  count?: number;
  style?: string;
}
export interface GeneratedImage {
  data: Buffer;
  mimeType: string;
  width: number;
  height: number;
  model: string;
  costUsd: number;
}
export interface ImageProvider {
  readonly name: string;
  generate(request: ImageRequest): Promise<GeneratedImage[]>;
}

export interface VoiceRequest {
  text: string;
  voiceId?: string;
  speed?: number;
  format?: 'mp3' | 'wav';
}
export interface GeneratedAudio {
  data: Buffer;
  mimeType: string;
  durationSec?: number;
  model: string;
  costUsd: number;
}
export interface VoiceProvider {
  readonly name: string;
  synthesize(request: VoiceRequest): Promise<GeneratedAudio>;
}

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  publishedAt?: Date;
  publisher?: string;
}
export interface SearchProvider {
  readonly name: string;
  search(query: string, options?: { limit?: number; freshness?: 'day' | 'week' | 'month' }): Promise<SearchResult[]>;
}

export interface StoredObject {
  key: string;
  /** Must be publicly resolvable — Meta fetches media from this URL. */
  publicUrl: string;
  sizeBytes: number;
  mimeType: string;
}
export interface StorageProvider {
  readonly name: string;
  put(key: string, data: Buffer, mimeType: string): Promise<StoredObject>;
  getPublicUrl(key: string): string;
  delete(key: string): Promise<void>;
}

export interface VideoRequest {
  prompt: string;
  durationSec: number;
  width?: number;
  height?: number;
}
export interface GeneratedVideo {
  data: Buffer;
  mimeType: string;
  durationSec: number;
  model: string;
  costUsd: number;
}
export interface VideoProvider {
  readonly name: string;
  generate(request: VideoRequest): Promise<GeneratedVideo>;
}

export interface TranscriptionSegment {
  text: string;
  startSec: number;
  endSec: number;
}
export interface TranscriptionProvider {
  readonly name: string;
  transcribe(audio: Buffer, mimeType: string): Promise<{ text: string; segments: TranscriptionSegment[] }>;
}
