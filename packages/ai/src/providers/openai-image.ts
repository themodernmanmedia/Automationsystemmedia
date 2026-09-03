import { AiError, ProviderNotConfiguredError, withRetry } from '@mmos/core';
import type { GeneratedImage, ImageProvider, ImageRequest } from '../types.js';

/** USD per generated image at 1024x1792 quality=standard. */
const COST_PER_IMAGE = 0.08;

export class OpenAiImageProvider implements ImageProvider {
  readonly name = 'openai-image';
  readonly #apiKey: string;
  readonly #baseUrl: string;

  constructor(config: { apiKey?: string; baseUrl?: string }) {
    if (!config.apiKey) throw new ProviderNotConfiguredError('OpenAI image', ['OPENAI_API_KEY']);
    this.#apiKey = config.apiKey;
    this.#baseUrl = config.baseUrl ?? 'https://api.openai.com/v1/images/generations';
  }

  async generate(request: ImageRequest): Promise<GeneratedImage[]> {
    // The API accepts a fixed set of sizes; pick the closest portrait/landscape.
    const width = request.width ?? 1024;
    const height = request.height ?? 1792;
    const size = height > width ? '1024x1792' : width > height ? '1792x1024' : '1024x1024';

    const body = await withRetry(
      async () => {
        const res = await fetch(this.#baseUrl, {
          method: 'POST',
          headers: { 'content-type': 'application/json', authorization: `Bearer ${this.#apiKey}` },
          body: JSON.stringify({
            model: 'dall-e-3',
            prompt: request.prompt,
            n: 1, // dall-e-3 accepts only n=1; callers needing more must loop
            size,
            response_format: 'b64_json',
          }),
        });
        if (!res.ok) {
          const text = await res.text();
          throw new AiError(`OpenAI image generation returned HTTP ${res.status}: ${text.slice(0, 300)}`, {
            retryable: res.status === 429 || res.status >= 500,
          });
        }
        return (await res.json()) as { data: Array<{ b64_json?: string }> };
      },
      { maxAttempts: 3, baseDelayMs: 2000 },
    );

    const [w, h] = size.split('x').map(Number) as [number, number];
    return body.data
      .filter((d) => d.b64_json)
      .map((d) => ({
        data: Buffer.from(d.b64_json as string, 'base64'),
        mimeType: 'image/png',
        width: w,
        height: h,
        model: 'dall-e-3',
        costUsd: COST_PER_IMAGE,
      }));
  }
}
