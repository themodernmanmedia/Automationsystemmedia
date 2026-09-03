'use client';

import { useState } from 'react';
import { clientFetch } from '@/lib/api';

const PLATFORM_NOTES: Record<string, string> = {
  INSTAGRAM: 'Requires an Instagram Professional account linked to a Facebook Page.',
  FACEBOOK: 'Connects every Page you administer. Each Page gets its own credentials.',
  TIKTOK: 'Posts will be private until your API client passes TikTok audit.',
};

export function ConnectButtons({
  providers,
}: {
  providers: Array<{ platform: string; available: boolean; reason?: string }>;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function connect(platform: string) {
    setBusy(platform);
    setError(null);
    try {
      const { authorizationUrl } = await clientFetch<{ authorizationUrl: string }>(
        `/oauth/${platform.toLowerCase()}/start`,
      );
      window.location.href = authorizationUrl;
    } catch (err) {
      setError((err as Error).message);
      setBusy(null);
    }
  }

  return (
    <div className="card">
      <div className="border-b border-ink-border px-5 py-4">
        <div className="label">Connect an account</div>
      </div>

      {error && <div className="border-b border-ink-border px-5 py-3 text-sm text-state-error">{error}</div>}

      <div className="grid gap-px bg-ink-border sm:grid-cols-3">
        {providers.map((provider) => (
          <div key={provider.platform} className="bg-ink-soft p-5">
            <div className="text-sm font-medium text-bone">{provider.platform}</div>
            <p className="mt-1 min-h-[2.5rem] text-xs leading-relaxed text-bone-muted">
              {provider.available ? PLATFORM_NOTES[provider.platform] : provider.reason}
            </p>
            <button
              className="btn-primary mt-3 w-full"
              // Disabled rather than hidden: the operator should see the
              // integration exists and learn exactly what is missing.
              disabled={!provider.available || busy !== null}
              onClick={() => connect(provider.platform)}
            >
              {busy === provider.platform ? 'Redirecting…' : `Connect ${provider.platform}`}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
