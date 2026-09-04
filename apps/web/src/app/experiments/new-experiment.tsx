'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { clientFetch } from '@/lib/api';

export function NewExperiment({
  variables,
  hasRunning,
}: {
  variables: string[];
  hasRunning: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const variantKeys = String(form.get('variants') ?? '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);

    setError(null);
    startTransition(async () => {
      try {
        await clientFetch('/experiments', {
          method: 'POST',
          body: JSON.stringify({
            name: form.get('name'),
            hypothesis: form.get('hypothesis'),
            variable: form.get('variable'),
            minSampleSize: Number(form.get('minSampleSize')),
            // "key: description" per line.
            variants: variantKeys.map((line) => {
              const [key, ...rest] = line.split(':');
              return {
                key: (key ?? '').trim(),
                description: rest.join(':').trim() || (key ?? '').trim(),
              };
            }),
          }),
        });
        setOpen(false);
        router.refresh();
      } catch (err) {
        setError((err as Error).message);
      }
    });
  }

  if (!open) {
    return (
      <div className="card card-pad flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-bone">New experiment</div>
          <p className="mt-1 text-xs text-bone-muted">
            {hasRunning
              ? 'One experiment is already running. Concurrent experiments confound each other, so it must finish first.'
              : 'Test one variable. Content generated while it runs is assigned to an arm automatically.'}
          </p>
        </div>
        <button className="btn-primary shrink-0" onClick={() => setOpen(true)}>
          Create experiment
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="card card-pad space-y-4">
      {error && <div className="text-sm text-state-error">{error}</div>}

      <div>
        <label htmlFor="name" className="label">Name</label>
        <input id="name" name="name" required defaultValue="Hook style"
          className="mt-1.5 w-full rounded-md border border-ink-border bg-ink px-3 py-2 text-sm text-bone outline-none focus:border-gold" />
      </div>

      <div>
        <label htmlFor="hypothesis" className="label">Hypothesis</label>
        <textarea id="hypothesis" name="hypothesis" required rows={2}
          defaultValue="Number-led hooks earn more saves than contrarian ones."
          className="mt-1.5 w-full rounded-md border border-ink-border bg-ink px-3 py-2 text-sm text-bone outline-none focus:border-gold" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="variable" className="label">Variable</label>
          <select id="variable" name="variable"
            className="mt-1.5 w-full rounded-md border border-ink-border bg-ink px-3 py-2 text-sm text-bone outline-none focus:border-gold">
            {variables.map((variable) => (
              <option key={variable} value={variable}>{variable}</option>
            ))}
          </select>
          <p className="mt-1 text-xs text-bone-dim">Exactly one, so the result is interpretable.</p>
        </div>

        <div>
          <label htmlFor="minSampleSize" className="label">Minimum posts per arm</label>
          <input id="minSampleSize" name="minSampleSize" type="number" min={5} max={200} defaultValue={10}
            className="mt-1.5 w-full rounded-md border border-ink-border bg-ink px-3 py-2 text-sm text-bone outline-none focus:border-gold" />
          <p className="mt-1 text-xs text-bone-dim">Below 5 nothing can be concluded.</p>
        </div>
      </div>

      <div>
        <label htmlFor="variants" className="label">Variants — one per line, &ldquo;key: description&rdquo;</label>
        <textarea id="variants" name="variants" required rows={3}
          defaultValue={'number_lead: Open with the statistic\ncontrarian: Open by contradicting a belief'}
          className="mt-1.5 w-full rounded-md border border-ink-border bg-ink px-3 py-2 font-mono text-xs text-bone outline-none focus:border-gold" />
        <p className="mt-1 text-xs text-bone-dim">Two to four arms. More splits a small sample too thinly.</p>
      </div>

      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={pending}>
          {pending ? 'Creating…' : 'Create as draft'}
        </button>
        <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  );
}
