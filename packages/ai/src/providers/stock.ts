/**
 * Licensed stock image providers.
 *
 * These exist so the system has a legitimate route to real photography. The
 * governing rule from the brief is that public accessibility is not a licence —
 * so every result carries the provenance the rights agent needs to make a
 * decision, and a provider that cannot supply that provenance is not used.
 *
 * Both Unsplash and Pexels licence their libraries for commercial use without
 * permission. Their API terms nevertheless require crediting the photographer,
 * so `attributionRequired` is set to true for both. That is the conservative
 * reading: the rights agent blocks an asset whose attribution is required but
 * missing, which is the correct failure direction.
 */
import { AiError, ProviderNotConfiguredError, withRetry } from '@mmos/core';

export interface StockImage {
  /** Direct URL to the image file, suitable for download. */
  url: string;
  /** Page for the asset on the provider, recorded as the provenance link. */
  sourceUrl: string;
  width: number;
  height: number;
  creator: string;
  creatorUrl?: string;
  license: string;
  attributionRequired: boolean;
  attributionText: string;
  description?: string;
  /** Unsplash requires this to be called when an image is actually used. */
  downloadTrackingUrl?: string;
}

export interface StockSearchOptions {
  limit?: number;
  /** Portrait suits 4:5 carousels and 9:16 reels; landscape suits neither. */
  orientation?: 'portrait' | 'landscape' | 'squarish';
}

export interface StockImageProvider {
  readonly name: string;
  search(query: string, options?: StockSearchOptions): Promise<StockImage[]>;
  /**
   * Reports that an image was used. Unsplash's API terms require this; for
   * providers with no such endpoint it is a no-op.
   */
  trackUsage?(image: StockImage): Promise<void>;
}

/* ------------------------------- Unsplash ------------------------------- */

export class UnsplashProvider implements StockImageProvider {
  readonly name = 'unsplash';
  readonly #accessKey: string;
  readonly #baseUrl: string;

  constructor(config: { accessKey?: string; baseUrl?: string }) {
    if (!config.accessKey) {
      throw new ProviderNotConfiguredError('Unsplash stock images', ['UNSPLASH_ACCESS_KEY']);
    }
    this.#accessKey = config.accessKey;
    this.#baseUrl = config.baseUrl ?? 'https://api.unsplash.com';
  }

  async search(query: string, options: StockSearchOptions = {}): Promise<StockImage[]> {
    const url = new URL('/search/photos', this.#baseUrl);
    url.searchParams.set('query', query);
    url.searchParams.set('per_page', String(options.limit ?? 10));
    if (options.orientation) url.searchParams.set('orientation', options.orientation);
    // Higher-quality results; the brand register does not suit snapshots.
    url.searchParams.set('content_filter', 'high');

    const body = await withRetry(
      async () => {
        const res = await fetch(url, {
          headers: {
            Authorization: `Client-ID ${this.#accessKey}`,
            'Accept-Version': 'v1',
          },
        });
        if (!res.ok) {
          throw new AiError(`Unsplash search returned HTTP ${res.status}`, {
            retryable: res.status === 429 || res.status >= 500,
          });
        }
        return (await res.json()) as {
          results?: Array<{
            urls?: { raw?: string; full?: string; regular?: string };
            links?: { html?: string; download_location?: string };
            width: number;
            height: number;
            description?: string | null;
            alt_description?: string | null;
            user?: { name?: string; links?: { html?: string } };
          }>;
        };
      },
      { maxAttempts: 3 },
    );

    return (body.results ?? [])
      .map((photo): StockImage | null => {
        const url = photo.urls?.full ?? photo.urls?.regular ?? photo.urls?.raw;
        if (!url) return null;
        const creator = photo.user?.name ?? 'Unknown';
        return {
          url,
          sourceUrl: photo.links?.html ?? url,
          width: photo.width,
          height: photo.height,
          creator,
          ...(photo.user?.links?.html ? { creatorUrl: photo.user.links.html } : {}),
          license: 'Unsplash License',
          // Their API terms require crediting the photographer.
          attributionRequired: true,
          attributionText: `Photo by ${creator} on Unsplash`,
          ...(photo.description || photo.alt_description
            ? { description: photo.description ?? photo.alt_description ?? '' }
            : {}),
          ...(photo.links?.download_location
            ? { downloadTrackingUrl: photo.links.download_location }
            : {}),
        };
      })
      .filter((image): image is StockImage => image !== null);
  }

  /** Required by the Unsplash API terms whenever an image is actually used. */
  async trackUsage(image: StockImage): Promise<void> {
    if (!image.downloadTrackingUrl) return;
    try {
      await fetch(image.downloadTrackingUrl, {
        headers: { Authorization: `Client-ID ${this.#accessKey}` },
      });
    } catch {
      // Compliance telemetry, not a publishing blocker.
    }
  }
}

/* -------------------------------- Pexels -------------------------------- */

export class PexelsProvider implements StockImageProvider {
  readonly name = 'pexels';
  readonly #apiKey: string;
  readonly #baseUrl: string;

  constructor(config: { apiKey?: string; baseUrl?: string }) {
    if (!config.apiKey) {
      throw new ProviderNotConfiguredError('Pexels stock images', ['PEXELS_API_KEY']);
    }
    this.#apiKey = config.apiKey;
    this.#baseUrl = config.baseUrl ?? 'https://api.pexels.com/v1';
  }

  async search(query: string, options: StockSearchOptions = {}): Promise<StockImage[]> {
    const url = new URL('/search', this.#baseUrl);
    url.searchParams.set('query', query);
    url.searchParams.set('per_page', String(options.limit ?? 10));
    if (options.orientation) url.searchParams.set('orientation', options.orientation);

    const body = await withRetry(
      async () => {
        const res = await fetch(url, { headers: { Authorization: this.#apiKey } });
        if (!res.ok) {
          throw new AiError(`Pexels search returned HTTP ${res.status}`, {
            retryable: res.status === 429 || res.status >= 500,
          });
        }
        return (await res.json()) as {
          photos?: Array<{
            src?: { original?: string; large2x?: string; large?: string };
            url?: string;
            width: number;
            height: number;
            alt?: string;
            photographer?: string;
            photographer_url?: string;
          }>;
        };
      },
      { maxAttempts: 3 },
    );

    return (body.photos ?? [])
      .map((photo): StockImage | null => {
        const url = photo.src?.original ?? photo.src?.large2x ?? photo.src?.large;
        if (!url) return null;
        const creator = photo.photographer ?? 'Unknown';
        return {
          url,
          sourceUrl: photo.url ?? url,
          width: photo.width,
          height: photo.height,
          creator,
          ...(photo.photographer_url ? { creatorUrl: photo.photographer_url } : {}),
          license: 'Pexels License',
          attributionRequired: true,
          attributionText: `Photo by ${creator} on Pexels`,
          ...(photo.alt ? { description: photo.alt } : {}),
        };
      })
      .filter((image): image is StockImage => image !== null);
  }
}
