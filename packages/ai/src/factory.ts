/**
 * Provider construction from configuration.
 *
 * An unconfigured provider throws ProviderNotConfiguredError at call time. It
 * never falls back to a stub that returns plausible-looking fake media — the
 * brief is explicit that unavailable functionality must fail visibly.
 */
import type { Config } from '@mmos/core';
import { ProviderNotConfiguredError } from '@mmos/core';
import type { ImageProvider, LlmProvider, SearchProvider, VoiceProvider } from './types.js';
import { PexelsProvider, UnsplashProvider, type StockImageProvider } from './providers/stock.js';
import { AnthropicProvider } from './providers/anthropic.js';
import { OpenAiProvider } from './providers/openai.js';
import { OpenAiImageProvider } from './providers/openai-image.js';
import { ElevenLabsVoiceProvider, OpenAiVoiceProvider } from './providers/voice.js';
import { BraveSearchProvider, TavilySearchProvider, RssSearchProvider, type FeedLogger } from './providers/search.js';

export function createLlmProvider(config: Config): LlmProvider {
  if (config.LLM_PROVIDER === 'openai') {
    return new OpenAiProvider({
      apiKey: config.OPENAI_API_KEY,
      model: config.OPENAI_MODEL,
      fastModel: config.OPENAI_FAST_MODEL,
    });
  }
  return new AnthropicProvider({
    apiKey: config.ANTHROPIC_API_KEY,
    model: config.ANTHROPIC_MODEL,
    fastModel: config.ANTHROPIC_FAST_MODEL,
  });
}

export function createImageProvider(config: Config): ImageProvider {
  switch (config.IMAGE_PROVIDER) {
    case 'openai':
      return new OpenAiImageProvider({ apiKey: config.OPENAI_API_KEY });
    case 'stability':
      throw new ProviderNotConfiguredError(
        'Stability image',
        ['STABILITY_API_KEY (adapter not implemented — use IMAGE_PROVIDER=openai)'],
      );
    default:
      throw new ProviderNotConfiguredError('Image', ['IMAGE_PROVIDER', 'OPENAI_API_KEY']);
  }
}

export function createVoiceProvider(config: Config): VoiceProvider {
  switch (config.VOICE_PROVIDER) {
    case 'elevenlabs':
      return new ElevenLabsVoiceProvider({
        apiKey: config.ELEVENLABS_API_KEY,
        voiceId: config.ELEVENLABS_VOICE_ID,
      });
    case 'openai':
      return new OpenAiVoiceProvider({ apiKey: config.OPENAI_API_KEY });
    default:
      throw new ProviderNotConfiguredError('Voice', ['VOICE_PROVIDER', 'ELEVENLABS_API_KEY']);
  }
}

/**
 * RSS needs no API key, so trend discovery works out of the box. It is used
 * alongside a keyed provider when one is configured, and alone when not.
 */
export function createSearchProviders(config: Config, logger?: FeedLogger): SearchProvider[] {
  const providers: SearchProvider[] = [];
  if (config.SEARCH_PROVIDER === 'brave' && config.BRAVE_SEARCH_API_KEY) {
    providers.push(new BraveSearchProvider({ apiKey: config.BRAVE_SEARCH_API_KEY }));
  }
  if (config.SEARCH_PROVIDER === 'tavily' && config.TAVILY_API_KEY) {
    providers.push(new TavilySearchProvider({ apiKey: config.TAVILY_API_KEY }));
  }
  if (config.RSS_FEEDS.length > 0) {
    providers.push(new RssSearchProvider({ feeds: config.RSS_FEEDS, ...(logger ? { logger } : {}) }));
  }
  if (providers.length === 0) {
    throw new ProviderNotConfiguredError('Search/trend', [
      'RSS_FEEDS (no API key required)',
      'or BRAVE_SEARCH_API_KEY',
      'or TAVILY_API_KEY',
    ]);
  }
  return providers;
}


/**
 * Licensed stock providers, in preference order.
 *
 * Returns an empty list rather than throwing: stock is optional, and a piece
 * with no imagery still publishes on the brand background.
 */
export function createStockProviders(config: Config): StockImageProvider[] {
  const providers: StockImageProvider[] = [];
  if (config.UNSPLASH_ACCESS_KEY) {
    providers.push(new UnsplashProvider({ accessKey: config.UNSPLASH_ACCESS_KEY }));
  }
  if (config.PEXELS_API_KEY) {
    providers.push(new PexelsProvider({ apiKey: config.PEXELS_API_KEY }));
  }
  return providers;
}
