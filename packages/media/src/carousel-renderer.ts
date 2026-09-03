/**
 * Renders designed carousel slides to real image files.
 *
 * One browser instance is reused across all slides in a carousel — launching
 * Chromium per slide would dominate the render time for a ten-slide post.
 */
import { chromium, type Browser } from 'playwright';
import { AppError, type Logger } from '@mmos/core';
import type { DesignedCarousel } from '@mmos/agents';
import { renderSlideHtml } from './slide-template.js';

export interface RenderedSlide {
  position: number;
  data: Buffer;
  mimeType: 'image/jpeg';
  width: number;
  height: number;
}

export interface CarouselRendererOptions {
  logger: Logger;
  /** Set when Chromium lives outside Playwright's default location. */
  executablePath?: string;
  /** JPEG quality. 90 keeps text crisp while staying under Instagram's 8 MB cap. */
  quality?: number;
}

export class CarouselRenderer {
  readonly #logger: Logger;
  readonly #executablePath?: string;
  readonly #quality: number;

  constructor(options: CarouselRendererOptions) {
    this.#logger = options.logger;
    if (options.executablePath) this.#executablePath = options.executablePath;
    this.#quality = options.quality ?? 90;
  }

  async render(
    carousel: DesignedCarousel,
    context: { brandName: string; logoUrl?: string; slideImages?: Record<number, string> },
  ): Promise<RenderedSlide[]> {
    let browser: Browser | undefined;
    try {
      browser = await chromium.launch({
        ...(this.#executablePath ? { executablePath: this.#executablePath } : {}),
        args: ['--no-sandbox', '--disable-dev-shm-usage'],
      });

      const page = await browser.newPage({
        viewport: { width: carousel.width, height: carousel.height },
        // Rendering at 1x with a large viewport keeps files small; the canvas
        // is already at Instagram's recommended pixel dimensions.
        deviceScaleFactor: 1,
      });

      const rendered: RenderedSlide[] = [];
      for (const slide of carousel.slides) {
        const html = renderSlideHtml({
          design: slide.design,
          width: carousel.width,
          height: carousel.height,
          brandName: context.brandName,
          ...(context.logoUrl ? { logoUrl: context.logoUrl } : {}),
          ...(context.slideImages?.[slide.position] ? { imageUrl: context.slideImages[slide.position] } : {}),
        });

        await page.setContent(html, { waitUntil: 'load' });
        // Web fonts load after `load`; screenshotting before they settle
        // produces a fallback-font slide, which is worse than a slow render.
        await page.evaluate('document.fonts.ready');

        const data = await page.screenshot({ type: 'jpeg', quality: this.#quality });
        rendered.push({
          position: slide.position,
          data,
          mimeType: 'image/jpeg',
          width: carousel.width,
          height: carousel.height,
        });
      }

      await page.close();
      this.#logger.info({ slides: rendered.length }, 'carousel rendered');
      return rendered;
    } catch (err) {
      throw new AppError(`Carousel rendering failed: ${(err as Error).message}`, {
        code: 'MEDIA_ERROR',
        retryable: true,
        cause: err,
      });
    } finally {
      await browser?.close();
    }
  }
}
