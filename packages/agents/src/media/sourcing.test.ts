/**
 * Media sourcing tests.
 *
 * The property that matters is not "did we get a picture" — it is that every
 * asset arrives with provenance the rights agent can actually evaluate. An
 * image without that is worse than no image, because it looks publishable.
 */
import { describe, expect, it, vi } from 'vitest';
import { createLogger } from '@mmos/core';
import type { GeneratedImage, ImageProvider, StockImage, StockImageProvider } from '@mmos/ai';
import { MediaSourcingAgent, buildStockQuery, collectAttributions } from './sourcing.js';
import { assessAssetRights, assessPostRights } from '../qa/rights.js';

const logger = createLogger({ level: 'silent' });

function fakeImageProvider(overrides: Partial<GeneratedImage> = {}): ImageProvider {
  return {
    name: 'fake-image',
    generate: vi.fn(async (): Promise<GeneratedImage[]> => [
      {
        data: Buffer.from('fake-png'),
        mimeType: 'image/png',
        width: 1024,
        height: 1792,
        model: 'fake-model',
        costUsd: 0.08,
        ...overrides,
      },
    ]),
  };
}

function fakeStock(images: StockImage[], name = 'fake-stock'): StockImageProvider {
  return {
    name,
    search: vi.fn(async () => images),
    trackUsage: vi.fn(async () => {}),
  };
}

const unsplashResult: StockImage = {
  url: 'https://images.example.com/photo.jpg',
  sourceUrl: 'https://unsplash.com/photos/abc',
  width: 1080,
  height: 1890,
  creator: 'Jane Doe',
  license: 'Unsplash License',
  attributionRequired: true,
  attributionText: 'Photo by Jane Doe on Unsplash',
  downloadTrackingUrl: 'https://api.unsplash.com/photos/abc/download',
};

describe('provenance is never missing', () => {
  it('marks generated imagery as unambiguously ours', async () => {
    const agent = new MediaSourcingAgent({ image: fakeImageProvider(), stock: [], logger });
    const result = await agent.source({ visualDirection: 'A dark boardroom' });

    expect(result.origin).toBe('GENERATED');
    expect(result.rights.assetSource).toBe('GENERATED');
    expect(result.rights.attributionRequired).toBe(false);
    // The whole point: the rights agent can clear it.
    expect(assessAssetRights(result.rights).publishable).toBe(true);
    expect(assessAssetRights(result.rights).risk).toBe('LOW');
  });

  it('carries the full licence chain for stock, including attribution', async () => {
    const agent = new MediaSourcingAgent({
      image: null,
      stock: [fakeStock([unsplashResult])],
      logger,
    });
    const result = await agent.source({ visualDirection: 'A dark boardroom' });

    expect(result.origin).toBe('STOCK_LICENSED');
    expect(result.rights).toMatchObject({
      assetSource: 'STOCK_LICENSED',
      license: 'Unsplash License',
      creator: 'Jane Doe',
      sourceUrl: 'https://unsplash.com/photos/abc',
      attributionRequired: true,
      attributionText: 'Photo by Jane Doe on Unsplash',
    });
    // Attribution required AND supplied, so it clears.
    expect(assessAssetRights(result.rights).publishable).toBe(true);
  });

  it('produces rights the agent blocks when attribution is required but absent', () => {
    // Guards the failure direction: a provider that cannot name the creator
    // must not yield a publishable asset.
    const assessment = assessAssetRights({
      assetSource: 'STOCK_LICENSED',
      license: 'Unsplash License',
      attributionRequired: true,
    });
    expect(assessment.publishable).toBe(false);
  });
});

describe('fallback behaviour', () => {
  it('falls back to stock when generation fails', async () => {
    const failing: ImageProvider = {
      name: 'broken',
      generate: vi.fn(async () => {
        throw new Error('quota exhausted');
      }),
    };
    const agent = new MediaSourcingAgent({
      image: failing,
      stock: [fakeStock([unsplashResult])],
      logger,
    });
    expect((await agent.source({ visualDirection: 'A boardroom' })).origin).toBe('STOCK_LICENSED');
  });

  it('degrades to the brand background rather than failing the post', async () => {
    const agent = new MediaSourcingAgent({ image: null, stock: [], logger });
    const result = await agent.source({ visualDirection: 'A boardroom' });

    expect(result.origin).toBe('NONE');
    // A missing image is not a publishing blocker.
    expect(assessAssetRights(result.rights).publishable).toBe(true);
  });

  it('tries the next provider when one errors', async () => {
    const broken: StockImageProvider = {
      name: 'broken',
      search: vi.fn(async () => {
        throw new Error('503');
      }),
    };
    const agent = new MediaSourcingAgent({
      image: null,
      stock: [broken, fakeStock([unsplashResult])],
      logger,
    });
    expect((await agent.source({ visualDirection: 'A boardroom' })).origin).toBe('STOCK_LICENSED');
  });

  it('honours the Unsplash requirement to report usage', async () => {
    const provider = fakeStock([unsplashResult]);
    const agent = new MediaSourcingAgent({ image: null, stock: [provider], logger });
    await agent.source({ visualDirection: 'A boardroom' });
    expect(provider.trackUsage).toHaveBeenCalledWith(unsplashResult);
  });

  it('skips generation when the caller asks for stock', async () => {
    const image = fakeImageProvider();
    const agent = new MediaSourcingAgent({ image, stock: [fakeStock([unsplashResult])], logger });
    const result = await agent.source({ visualDirection: 'A boardroom', preferStock: true });

    expect(result.origin).toBe('STOCK_LICENSED');
    expect(image.generate).not.toHaveBeenCalled();
  });
});

describe('choosing among results', () => {
  it('prefers the closest aspect ratio, so less is cropped away', async () => {
    const landscape: StockImage = { ...unsplashResult, url: 'wide.jpg', width: 1920, height: 1080 };
    const portrait: StockImage = { ...unsplashResult, url: 'tall.jpg', width: 1080, height: 1920 };

    const agent = new MediaSourcingAgent({
      image: null,
      stock: [fakeStock([landscape, portrait])],
      logger,
    });
    const result = await agent.source({ visualDirection: 'x', width: 1080, height: 1920 });
    expect(result.remoteUrl).toBe('tall.jpg');
  });
});

describe('buildStockQuery', () => {
  it('reduces a human visual direction to searchable nouns', () => {
    const query = buildStockQuery(
      'A wide shot of a dark boardroom at night, looking towards the window',
      ['nvidia', 'earnings'],
    );
    expect(query).toContain('nvidia');
    expect(query).toContain('boardroom');
    // Treatment words retrieve badly on stock search engines.
    expect(query).not.toContain('shot');
    expect(query).not.toContain('wide');
    expect(query).not.toContain('the');
  });

  it('works with no keywords', () => {
    expect(buildStockQuery('A dark boardroom')).toContain('boardroom');
  });
});

describe('collectAttributions', () => {
  it('gathers what a post owes, without duplicates', () => {
    const attributions = collectAttributions([
      { assetSource: 'STOCK_LICENSED', attributionRequired: true, attributionText: 'Photo by Jane Doe on Unsplash' },
      { assetSource: 'STOCK_LICENSED', attributionRequired: true, attributionText: 'Photo by Jane Doe on Unsplash' },
      { assetSource: 'STOCK_LICENSED', attributionRequired: true, attributionText: 'Photo by Sam Roe on Pexels' },
      { assetSource: 'GENERATED', attributionRequired: false },
    ]);
    expect(attributions).toEqual(['Photo by Jane Doe on Unsplash', 'Photo by Sam Roe on Pexels']);
  });

  it('returns nothing when everything is generated', () => {
    expect(collectAttributions([{ assetSource: 'GENERATED', attributionRequired: false }])).toEqual([]);
  });
});

describe('a whole post of sourced assets', () => {
  it('clears the rights gate when every asset is properly sourced', async () => {
    const agent = new MediaSourcingAgent({
      image: fakeImageProvider(),
      stock: [fakeStock([unsplashResult])],
      logger,
    });
    const assets = await Promise.all([
      agent.source({ visualDirection: 'A boardroom' }),
      agent.source({ visualDirection: 'A trading floor', preferStock: true }),
    ]);

    const verdict = assessPostRights(assets.map((a) => a.rights));
    expect(verdict.publishable).toBe(true);
    expect(verdict.blocking).toEqual([]);
  });
});
