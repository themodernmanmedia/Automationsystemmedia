/**
 * Adapter factory.
 *
 * Adapters are constructed only when their credentials are present, so a
 * missing META_APP_ID surfaces as "Instagram is not configured" in the UI
 * rather than as a runtime crash inside a worker.
 */
import type { Config } from '@mmos/core';
import { NotFoundError } from '@mmos/core';
import type { PlatformAdapter, PlatformName } from './types.js';
import { InstagramAdapter } from './instagram/adapter.js';
import { TikTokAdapter } from './tiktok/adapter.js';
import { FacebookAdapter } from './facebook/adapter.js';

export class AdapterRegistry {
  readonly #adapters = new Map<PlatformName, PlatformAdapter>();

  constructor(config: Config) {
    if (config.META_APP_ID && config.META_APP_SECRET && config.META_REDIRECT_URI) {
      const meta = {
        appId: config.META_APP_ID,
        appSecret: config.META_APP_SECRET,
        redirectUri: config.META_REDIRECT_URI,
        graphVersion: config.META_GRAPH_VERSION,
      };
      this.#adapters.set('INSTAGRAM', new InstagramAdapter(meta));
      this.#adapters.set('FACEBOOK', new FacebookAdapter(meta));
    }
    if (config.TIKTOK_CLIENT_KEY && config.TIKTOK_CLIENT_SECRET && config.TIKTOK_REDIRECT_URI) {
      this.#adapters.set(
        'TIKTOK',
        new TikTokAdapter({
          clientKey: config.TIKTOK_CLIENT_KEY,
          clientSecret: config.TIKTOK_CLIENT_SECRET,
          redirectUri: config.TIKTOK_REDIRECT_URI,
        }),
      );
    }
  }

  get(platform: PlatformName): PlatformAdapter {
    const adapter = this.#adapters.get(platform);
    if (!adapter) {
      throw new NotFoundError(
        `No configured adapter for ${platform}. Set the platform credentials in your environment (see .env.example)`,
      );
    }
    return adapter;
  }

  has(platform: PlatformName): boolean {
    return this.#adapters.has(platform);
  }

  configured(): PlatformName[] {
    return [...this.#adapters.keys()];
  }
}
