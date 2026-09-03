/**
 * AGENT 8 — CAROUSEL DESIGNER.
 *
 * Turns a written carousel into a full design specification per slide. This is
 * deliberately deterministic rather than model-generated: visual consistency is
 * what makes a brand recognizable without its name attached, and a model asked
 * to "design a slide" produces a different look every time.
 *
 * The design system encodes the brief's brand: black, off-white, gold, dark
 * gray — luxury magazine meets business media.
 */
import { BRAND_COLORS, DEFAULT_BRAND } from '@mmos/core';
import type { CarouselScript } from '@mmos/contracts';

export interface SlideDesign {
  background: string;
  backgroundStyle: 'SOLID' | 'GRADIENT' | 'IMAGE_OVERLAY';
  headline: string;
  headlineColor: string;
  headlineFont: string;
  headlineSize: number;
  headlineWeight: number;
  body: string;
  bodyColor: string;
  bodyFont: string;
  bodySize: number;
  imagePosition: 'NONE' | 'FULL_BLEED' | 'TOP' | 'BOTTOM' | 'RIGHT';
  imagePrompt?: string;
  alignment: 'LEFT' | 'CENTER';
  spacing: { top: number; right: number; bottom: number; left: number };
  accent: { color: string; style: 'RULE' | 'BAR' | 'NUMBER' | 'NONE'; position: 'TOP' | 'BOTTOM' | 'LEFT' };
  logoPosition: 'TOP_LEFT' | 'TOP_RIGHT' | 'BOTTOM_LEFT' | 'BOTTOM_RIGHT' | 'NONE';
  pageNumber: { show: boolean; text: string; color: string };
  visualHierarchy: string[];
}

export interface DesignedSlide {
  position: number;
  role: string;
  headline: string;
  body: string;
  design: SlideDesign;
}

export interface DesignedCarousel {
  slides: DesignedSlide[];
  aspectRatio: string;
  width: number;
  height: number;
  coverSlideIndex: number;
}

/** 4:5 is Instagram's tallest permitted feed ratio — maximum screen real estate. */
const CANVAS = { width: 1080, height: 1350 };

/**
 * Type scale. The cover is dramatically larger than body slides: a cover has one
 * job — stop the scroll — and competing elements on it dilute that.
 */
const TYPE_SCALE = {
  HOOK: { headline: 96, body: 34, weight: 700 },
  CONTEXT: { headline: 58, body: 32, weight: 600 },
  POINT: { headline: 54, body: 32, weight: 600 },
  TAKEAWAY: { headline: 64, body: 34, weight: 700 },
  CTA: { headline: 72, body: 34, weight: 700 },
} as const;

export interface DesignOptions {
  colors?: Record<string, string>;
  fonts?: { display: string; body: string };
  logoPosition?: SlideDesign['logoPosition'];
}

export function designCarousel(script: CarouselScript, options: DesignOptions = {}): DesignedCarousel {
  const colors = { ...BRAND_COLORS, ...options.colors };
  const fonts = options.fonts ?? { display: DEFAULT_BRAND.fonts.display, body: DEFAULT_BRAND.fonts.body };
  const total = script.slides.length;

  const slides: DesignedSlide[] = script.slides.map((slide, index) => {
    const role = slide.role;
    const scale = TYPE_SCALE[role as keyof typeof TYPE_SCALE] ?? TYPE_SCALE.POINT;
    const isCover = index === 0;
    const isCta = role === 'CTA';

    // Cover and CTA invert to black for weight; interior slides sit on off-white
    // so a long carousel stays readable rather than becoming a wall of contrast.
    const inverted = isCover || isCta;
    const background = inverted ? colors['black'] ?? BRAND_COLORS.black : colors['offWhite'] ?? BRAND_COLORS.offWhite;
    const foreground = inverted ? colors['offWhite'] ?? BRAND_COLORS.offWhite : colors['black'] ?? BRAND_COLORS.black;
    const gold = colors['gold'] ?? BRAND_COLORS.gold;

    // Long headlines get stepped down rather than overflowing the canvas.
    const headlineSize = fitHeadline(slide.headline, scale.headline);

    const design: SlideDesign = {
      background,
      backgroundStyle: isCover ? 'IMAGE_OVERLAY' : 'SOLID',
      headline: slide.headline,
      headlineColor: foreground,
      headlineFont: fonts.display,
      headlineSize,
      headlineWeight: scale.weight,
      body: slide.body,
      bodyColor: inverted ? withAlpha(colors['offWhite'] ?? BRAND_COLORS.offWhite, 0.85) : withAlpha(colors['darkGray'] ?? BRAND_COLORS.darkGray, 0.9),
      bodyFont: fonts.body,
      bodySize: scale.body,
      imagePosition: isCover ? 'FULL_BLEED' : slide.visualNote ? 'TOP' : 'NONE',
      ...(slide.visualNote ? { imagePrompt: buildImagePrompt(slide.visualNote) } : {}),
      alignment: isCover || isCta ? 'LEFT' : 'LEFT',
      spacing: { top: 96, right: 88, bottom: 96, left: 88 },
      accent: {
        color: gold,
        style: isCover ? 'BAR' : role === 'POINT' ? 'NUMBER' : 'RULE',
        position: isCover ? 'BOTTOM' : 'TOP',
      },
      logoPosition: options.logoPosition ?? (isCover ? 'TOP_LEFT' : 'BOTTOM_LEFT'),
      pageNumber: {
        // No page number on the cover: it competes with the hook.
        show: !isCover,
        text: `${index + 1} / ${total}`,
        color: withAlpha(inverted ? colors['offWhite'] ?? BRAND_COLORS.offWhite : colors['darkGray'] ?? BRAND_COLORS.darkGray, 0.5),
      },
      visualHierarchy: isCover
        ? ['headline', 'accent', 'logo']
        : ['accent', 'headline', 'body', 'pageNumber', 'logo'],
    };

    return { position: index, role, headline: slide.headline, body: slide.body, design };
  });

  return {
    slides,
    aspectRatio: '4:5',
    width: CANVAS.width,
    height: CANVAS.height,
    coverSlideIndex: 0,
  };
}

/**
 * Steps type down for longer headlines. Cheap approximation of real text
 * measurement, but it reliably prevents the single worst design failure:
 * a headline running off the canvas.
 */
function fitHeadline(text: string, baseSize: number): number {
  const length = text.length;
  if (length <= 28) return baseSize;
  if (length <= 45) return Math.round(baseSize * 0.82);
  if (length <= 65) return Math.round(baseSize * 0.68);
  return Math.round(baseSize * 0.56);
}

/** Keeps generated imagery inside the brand's visual register. */
function buildImagePrompt(visualNote: string): string {
  return `${visualNote}. Editorial photography for a premium men's business magazine. Dramatic directional lighting, deep shadows, muted desaturated palette with warm gold highlights. Cinematic, restrained, expensive. No text, no words, no logos, no watermarks.`;
}

function withAlpha(hex: string, alpha: number): string {
  const value = Math.round(Math.max(0, Math.min(1, alpha)) * 255)
    .toString(16)
    .padStart(2, '0');
  return `${hex}${value}`;
}
