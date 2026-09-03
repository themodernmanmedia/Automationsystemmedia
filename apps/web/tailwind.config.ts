import type { Config } from 'tailwindcss';

/**
 * The brand system, expressed as design tokens. The dashboard shares the
 * content brand's palette so the tool feels like part of the same product.
 */
export default {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#080808', soft: '#0E0E0E', raised: '#141414', border: '#1F1F1F' },
        bone: { DEFAULT: '#F4F1E8', muted: '#A8A49A', dim: '#6B6862' },
        gold: { DEFAULT: '#C9A227', soft: '#E0BE4A', dim: '#8A6F1B' },
        state: { ok: '#3E9B6B', warn: '#C9A227', error: '#C0483C', idle: '#4A4A4A' },
      },
      fontFamily: {
        display: ['var(--font-display)', 'Georgia', 'serif'],
        sans: ['var(--font-body)', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      letterSpacing: { tightest: '-0.04em' },
    },
  },
  plugins: [],
} satisfies Config;
