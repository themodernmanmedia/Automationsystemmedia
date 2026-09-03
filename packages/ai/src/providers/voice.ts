import { AiError, ProviderNotConfiguredError, withRetry } from '@mmos/core';
import type { GeneratedAudio, VoiceProvider, VoiceRequest } from '../types.js';

/** ElevenLabs bills per character; this is a mid-tier plan approximation. */
const ELEVENLABS_COST_PER_1K_CHARS = 0.18;
const OPENAI_TTS_COST_PER_1K_CHARS = 0.015;

export class ElevenLabsVoiceProvider implements VoiceProvider {
  readonly name = 'elevenlabs';
  readonly #apiKey: string;
  readonly #voiceId: string;
  readonly #baseUrl: string;

  constructor(config: { apiKey?: string; voiceId?: string; baseUrl?: string }) {
    if (!config.apiKey) {
      throw new ProviderNotConfiguredError('ElevenLabs voice', ['ELEVENLABS_API_KEY']);
    }
    if (!config.voiceId) {
      throw new ProviderNotConfiguredError('ElevenLabs voice', ['ELEVENLABS_VOICE_ID']);
    }
    this.#apiKey = config.apiKey;
    this.#voiceId = config.voiceId;
    this.#baseUrl = config.baseUrl ?? 'https://api.elevenlabs.io/v1/text-to-speech';
  }

  async synthesize(request: VoiceRequest): Promise<GeneratedAudio> {
    const voiceId = request.voiceId ?? this.#voiceId;
    const buffer = await withRetry(
      async () => {
        const res = await fetch(`${this.#baseUrl}/${voiceId}`, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            'xi-api-key': this.#apiKey,
            accept: 'audio/mpeg',
          },
          body: JSON.stringify({
            text: request.text,
            model_id: 'eleven_multilingual_v2',
            voice_settings: { stability: 0.5, similarity_boost: 0.75 },
          }),
        });
        if (!res.ok) {
          const text = await res.text();
          throw new AiError(`ElevenLabs returned HTTP ${res.status}: ${text.slice(0, 300)}`, {
            retryable: res.status === 429 || res.status >= 500,
          });
        }
        return Buffer.from(await res.arrayBuffer());
      },
      { maxAttempts: 3, baseDelayMs: 1500 },
    );

    return {
      data: buffer,
      mimeType: 'audio/mpeg',
      model: 'eleven_multilingual_v2',
      costUsd: (request.text.length / 1000) * ELEVENLABS_COST_PER_1K_CHARS,
    };
  }
}

export class OpenAiVoiceProvider implements VoiceProvider {
  readonly name = 'openai-tts';
  readonly #apiKey: string;
  readonly #baseUrl: string;

  constructor(config: { apiKey?: string; baseUrl?: string }) {
    if (!config.apiKey) throw new ProviderNotConfiguredError('OpenAI voice', ['OPENAI_API_KEY']);
    this.#apiKey = config.apiKey;
    this.#baseUrl = config.baseUrl ?? 'https://api.openai.com/v1/audio/speech';
  }

  async synthesize(request: VoiceRequest): Promise<GeneratedAudio> {
    const buffer = await withRetry(
      async () => {
        const res = await fetch(this.#baseUrl, {
          method: 'POST',
          headers: { 'content-type': 'application/json', authorization: `Bearer ${this.#apiKey}` },
          body: JSON.stringify({
            model: 'tts-1-hd',
            input: request.text,
            // A lower, measured voice fits the brand's confident register.
            voice: request.voiceId ?? 'onyx',
            response_format: request.format ?? 'mp3',
            speed: request.speed ?? 1.0,
          }),
        });
        if (!res.ok) {
          const text = await res.text();
          throw new AiError(`OpenAI TTS returned HTTP ${res.status}: ${text.slice(0, 300)}`, {
            retryable: res.status === 429 || res.status >= 500,
          });
        }
        return Buffer.from(await res.arrayBuffer());
      },
      { maxAttempts: 3, baseDelayMs: 1500 },
    );

    return {
      data: buffer,
      mimeType: request.format === 'wav' ? 'audio/wav' : 'audio/mpeg',
      model: 'tts-1-hd',
      costUsd: (request.text.length / 1000) * OPENAI_TTS_COST_PER_1K_CHARS,
    };
  }
}
