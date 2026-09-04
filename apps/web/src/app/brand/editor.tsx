'use client';

import { useMemo, useState, useTransition } from 'react';
import { clientFetch, type BrandResponse } from '@/lib/api';

type Brand = NonNullable<BrandResponse['brand']>;

export function BrandEditor({ brand, defaults }: { brand: Brand; defaults: BrandResponse['defaults'] }) {
  const [mix, setMix] = useState<Record<string, number>>(brand.contentMix);
  const [ctaStyle, setCtaStyle] = useState(brand.ctaStyle);
  const [slideCount, setSlideCount] = useState(brand.defaultSlideCount);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const mixTotal = useMemo(
    () => Object.values(mix).reduce((sum, value) => sum + value, 0),
    [mix],
  );
  // The API rejects a mix that does not total 100, because a planner working
  // from an invalid distribution would skew silently.
  const mixValid = Math.abs(mixTotal - 100) <= 0.5;

  function save() {
    setError(null);
    setSaved(false);
    startTransition(async () => {
      try {
        const result = (await clientFetch(`/brand/${brand.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ contentMix: mix, ctaStyle, defaultSlideCount: slideCount }),
        })) as { error?: string };
        if (result.error) setError(result.error);
        else setSaved(true);
      } catch (err) {
        setError((err as Error).message);
      }
    });
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="card card-pad border-state-error/40">
          <div className="text-sm text-state-error">{error}</div>
        </div>
      )}
      {saved && (
        <div className="card card-pad border-state-ok/40">
          <div className="text-sm text-state-ok">
            Saved. Content generated from now on uses these settings.
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Identity — read-only here, since changing it changes rendered output */}
        <div className="card">
          <div className="border-b border-ink-border px-5 py-4">
            <div className="label">Visual identity</div>
            <p className="mt-1 text-xs text-bone-dim">
              Used by the carousel designer for every slide it renders.
            </p>
          </div>
          <div className="space-y-4 p-5">
            <div>
              <div className="label">Palette</div>
              <div className="mt-2 flex flex-wrap gap-3">
                {Object.entries(brand.colors).map(([name, value]) => (
                  <div key={name} className="flex items-center gap-2">
                    <span
                      className="h-8 w-8 rounded border border-ink-border"
                      style={{ background: value }}
                    />
                    <div>
                      <div className="text-xs text-bone">{name}</div>
                      <div className="font-mono text-[11px] text-bone-dim">{value}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="label">Typography</div>
              <div className="mt-1.5 text-sm text-bone-muted">
                {Object.entries(brand.fonts).map(([role, family]) => (
                  <div key={role}>
                    <span className="text-bone-dim">{role}:</span> {family}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="label">Visual direction</div>
              <p className="mt-1.5 text-sm text-bone-muted">{brand.visualDirection}</p>
            </div>
          </div>
        </div>

        {/* Voice */}
        <div className="card">
          <div className="border-b border-ink-border px-5 py-4">
            <div className="label">Voice</div>
            <p className="mt-1 text-xs text-bone-dim">
              Every writing agent receives this, and the brand QA agent judges against it.
            </p>
          </div>
          <div className="space-y-4 p-5">
            <div>
              <div className="label">Tone</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {brand.tone.map((word) => (
                  <span key={word} className="pill border-ink-border text-bone-muted">{word}</span>
                ))}
              </div>
            </div>

            <div>
              <div className="label">Never produce</div>
              <p className="mt-1 text-xs text-bone-dim">
                Enforced by the safety agent, not merely suggested in a prompt.
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {brand.avoidList.map((item) => (
                  <span key={item} className="pill border-state-error/30 text-state-error">{item}</span>
                ))}
              </div>
            </div>

            <div>
              <label htmlFor="cta" className="label">Call to action</label>
              <input
                id="cta"
                value={ctaStyle}
                onChange={(event) => setCtaStyle(event.target.value)}
                className="mt-1.5 w-full rounded-md border border-ink-border bg-ink px-3 py-2 text-sm text-bone outline-none focus:border-gold"
              />
            </div>

            <div>
              <label htmlFor="slides" className="label">Default slide count</label>
              <input
                id="slides"
                type="number"
                min={3}
                max={10}
                value={slideCount}
                onChange={(event) => setSlideCount(Number(event.target.value))}
                className="mt-1.5 w-24 rounded-md border border-ink-border bg-ink px-3 py-2 text-sm text-bone outline-none focus:border-gold"
              />
              <p className="mt-1 text-xs text-bone-dim">
                A target, not a rule — the writer uses what the material justifies.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Content mix */}
      <div className="card">
        <div className="flex items-center justify-between border-b border-ink-border px-5 py-4">
          <div>
            <div className="label">Content mix</div>
            <p className="mt-1 text-xs text-bone-dim">
              Target share per category. The planner prioritises whichever is most under-served, and
              the learning engine adjusts these within bounds as performance data arrives.
            </p>
          </div>
          <div className={`text-right ${mixValid ? 'text-state-ok' : 'text-state-error'}`}>
            <div className="font-display text-2xl tracking-tightest">{mixTotal.toFixed(1)}%</div>
            <div className="text-[11px] uppercase tracking-wider">
              {mixValid ? 'valid' : 'must total 100'}
            </div>
          </div>
        </div>

        <div className="grid gap-px bg-ink-border sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(mix).map(([category, value]) => (
            <div key={category} className="bg-ink-soft p-4">
              <div className="flex items-center justify-between">
                <label htmlFor={`mix-${category}`} className="text-sm text-bone">{category}</label>
                <span className="font-mono text-sm text-gold">{value.toFixed(1)}%</span>
              </div>
              <input
                id={`mix-${category}`}
                type="range"
                min={0}
                max={40}
                step={0.5}
                value={value}
                onChange={(event) =>
                  setMix({ ...mix, [category]: Number(event.target.value) })
                }
                className="mt-2 w-full accent-gold"
              />
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-border px-5 py-4">
          <button
            className="btn-ghost"
            disabled={pending}
            onClick={() => setMix(defaults.contentMix)}
          >
            Reset to defaults
          </button>
          <button className="btn-primary" disabled={pending || !mixValid} onClick={save}>
            {pending ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </div>

      {/* Scoring weights — read-only, because learning owns them */}
      <div className="card">
        <div className="border-b border-ink-border px-5 py-4">
          <div className="label">Topic scoring weights</div>
          <p className="mt-1 text-xs leading-relaxed text-bone-dim">
            How much each dimension counts when ranking topics. The learning engine adjusts these
            from measured performance, in bounded steps, so they are shown rather than edited here —
            a manual change would be overwritten on the next cycle.
          </p>
        </div>
        <div className="grid gap-px bg-ink-border sm:grid-cols-3 lg:grid-cols-4">
          {Object.entries(brand.scoringWeights)
            .sort(([, a], [, b]) => b - a)
            .map(([dimension, weight]) => (
              <div key={dimension} className="bg-ink-soft px-4 py-3">
                <div className="text-[11px] uppercase tracking-wider text-bone-dim">{dimension}</div>
                <div className="mt-1 font-display text-lg text-bone">
                  {(weight * 100).toFixed(1)}%
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
