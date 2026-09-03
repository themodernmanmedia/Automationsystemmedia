/**
 * Carousel slide rendering.
 *
 * Slides are rendered by laying the design specification out as HTML and
 * screenshotting it with headless Chromium. That choice is deliberate: a
 * browser gives real typography — web fonts, kerning, automatic line breaking,
 * proper text wrapping — which is exactly what separates a slide that looks
 * designed from one that looks generated. A canvas drawing library would need
 * all of that reimplemented badly.
 */
import type { SlideDesign } from '@mmos/agents';

export interface SlideRenderInput {
  design: SlideDesign;
  width: number;
  height: number;
  brandName: string;
  logoUrl?: string;
  /** Data URI or public URL for the slide's background/feature image. */
  imageUrl?: string;
}

/**
 * Builds a fully self-contained HTML document for one slide. Fonts come from
 * Google Fonts; everything else is inline, so rendering needs no local assets.
 */
export function renderSlideHtml(input: SlideRenderInput): string {
  const { design, width, height, brandName, imageUrl } = input;

  const accentMarkup = buildAccent(design);
  const hasImage = design.imagePosition !== 'NONE' && Boolean(imageUrl);
  const fullBleed = hasImage && design.imagePosition === 'FULL_BLEED';

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=${encodeURIComponent(design.headlineFont)}:wght@600;700;800&family=${encodeURIComponent(design.bodyFont)}:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: ${width}px; height: ${height}px; }
  body {
    background: ${design.background};
    font-family: '${design.bodyFont}', system-ui, sans-serif;
    position: relative;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
  }
  .bg-image {
    position: absolute; inset: 0;
    background-image: url('${imageUrl ?? ''}');
    background-size: cover; background-position: center;
    /* Held well back so the headline always wins the contrast fight. */
    opacity: ${fullBleed ? 0.34 : 1};
  }
  .scrim {
    position: absolute; inset: 0;
    background: linear-gradient(160deg, ${design.background}E6 0%, ${design.background}B3 45%, ${design.background}F2 100%);
  }
  .top-image {
    position: absolute; top: 0; left: 0; right: 0; height: ${Math.round(height * 0.38)}px;
    background-image: url('${imageUrl ?? ''}');
    background-size: cover; background-position: center;
  }
  .top-image::after {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(to bottom, transparent 55%, ${design.background} 100%);
  }
  .frame {
    position: relative; z-index: 2;
    display: flex; flex-direction: column;
    height: 100%;
    padding: ${design.spacing.top}px ${design.spacing.right}px ${design.spacing.bottom}px ${design.spacing.left}px;
    ${design.imagePosition === 'TOP' && hasImage ? `padding-top: ${Math.round(height * 0.38) + 48}px;` : ''}
    text-align: ${design.alignment === 'CENTER' ? 'center' : 'left'};
  }
  .body-block { flex: 1; display: flex; flex-direction: column; justify-content: center; }
  .headline {
    font-family: '${design.headlineFont}', Georgia, serif;
    font-weight: ${design.headlineWeight};
    font-size: ${design.headlineSize}px;
    line-height: 1.06;
    letter-spacing: -0.028em;
    color: ${design.headlineColor};
    /* Balanced wrapping avoids a lone orphan word on the last line. */
    text-wrap: balance;
  }
  .body {
    margin-top: 28px;
    font-size: ${design.bodySize}px;
    line-height: 1.5;
    font-weight: 400;
    color: ${design.bodyColor};
    max-width: 92%;
    ${design.alignment === 'CENTER' ? 'margin-left: auto; margin-right: auto;' : ''}
  }
  .accent-bar { width: 96px; height: 6px; background: ${design.accent.color}; border-radius: 2px; }
  .accent-rule { width: 56px; height: 2px; background: ${design.accent.color}; opacity: 0.85; }
  .accent-number {
    font-family: '${design.headlineFont}', Georgia, serif;
    font-size: 26px; font-weight: 700; letter-spacing: 0.16em;
    color: ${design.accent.color};
  }
  .accent-top { margin-bottom: 34px; }
  .accent-bottom { margin-top: 38px; }
  .footer {
    display: flex; align-items: center; justify-content: space-between;
    font-size: 19px; letter-spacing: 0.16em; text-transform: uppercase; font-weight: 500;
  }
  .brand { color: ${design.accent.color}; }
  .page-number { color: ${design.pageNumber.color}; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>
  ${fullBleed ? `<div class="bg-image"></div><div class="scrim"></div>` : ''}
  ${design.imagePosition === 'TOP' && hasImage ? `<div class="top-image"></div>` : ''}
  <div class="frame">
    ${design.accent.position === 'TOP' ? `<div class="accent-top">${accentMarkup}</div>` : ''}
    <div class="body-block">
      <h1 class="headline">${escapeHtml(design.headline)}</h1>
      ${design.body ? `<p class="body">${escapeHtml(design.body)}</p>` : ''}
    </div>
    ${design.accent.position === 'BOTTOM' ? `<div class="accent-bottom">${accentMarkup}</div>` : ''}
    <div class="footer">
      <span class="brand">${escapeHtml(brandName)}</span>
      ${design.pageNumber.show ? `<span class="page-number">${escapeHtml(design.pageNumber.text)}</span>` : '<span></span>'}
    </div>
  </div>
</body>
</html>`;
}

function buildAccent(design: SlideDesign): string {
  switch (design.accent.style) {
    case 'BAR':
      return '<div class="accent-bar"></div>';
    case 'RULE':
      return '<div class="accent-rule"></div>';
    case 'NUMBER':
      return `<div class="accent-number">${escapeHtml(design.pageNumber.text.split('/')[0]?.trim() ?? '')}</div>`;
    default:
      return '';
  }
}

/** Content is model-generated, so it is escaped before entering the document. */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
