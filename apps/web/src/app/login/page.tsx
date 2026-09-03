'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { clientFetch } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    const form = new FormData(event.currentTarget);
    const payload =
      mode === 'login'
        ? { email: form.get('email'), password: form.get('password') }
        : {
            email: form.get('email'),
            password: form.get('password'),
            name: form.get('name'),
            organizationName: form.get('organizationName'),
          };

    try {
      await clientFetch(`/auth/${mode}`, { method: 'POST', body: JSON.stringify(payload) });
      router.push('/');
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="font-display text-2xl tracking-tightest text-bone">The Modern Man</div>
          <div className="mt-1 text-[10px] font-medium uppercase tracking-[0.2em] text-gold">
            Operating System
          </div>
        </div>

        <form onSubmit={submit} className="card card-pad space-y-4">
          {mode === 'register' && (
            <>
              <Field name="name" label="Your name" />
              <Field name="organizationName" label="Organization" defaultValue="The Modern Man" />
            </>
          )}
          <Field name="email" label="Email" type="email" />
          <Field
            name="password"
            label="Password"
            type="password"
            hint={mode === 'register' ? 'At least 12 characters' : undefined}
          />

          {error && <div className="text-sm text-state-error">{error}</div>}

          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? 'Working…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>

          <button
            type="button"
            className="w-full text-center text-xs text-bone-dim hover:text-bone-muted"
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null); }}
          >
            {mode === 'login' ? 'First time? Create the owner account' : 'Already set up? Sign in'}
          </button>
        </form>

        <p className="mt-4 text-center text-xs leading-relaxed text-bone-dim">
          Registration is available only until the first account exists.
        </p>
      </div>
    </div>
  );
}

function Field({ name, label, type = 'text', hint, defaultValue }: {
  name: string;
  label: string;
  type?: string;
  hint?: string;
  defaultValue?: string;
}) {
  return (
    <div>
      <label htmlFor={name} className="label">{label}</label>
      <input
        id={name}
        name={name}
        type={type}
        required
        defaultValue={defaultValue}
        className="mt-1.5 w-full rounded-md border border-ink-border bg-ink px-3 py-2 text-sm text-bone
                   outline-none transition-colors focus:border-gold"
      />
      {hint && <p className="mt-1 text-xs text-bone-dim">{hint}</p>}
    </div>
  );
}
