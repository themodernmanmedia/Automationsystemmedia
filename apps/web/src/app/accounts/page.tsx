import { headers } from 'next/headers';
import { apiFetch, ApiError, type AccountsResponse } from '@/lib/api';
import { PageHeader, StatusPill, MetricValue, EmptyState, ErrorPanel, Unavailable } from '@/components/ui';
import { ConnectButtons } from './connect';

export const dynamic = 'force-dynamic';

const TOKEN_TONE = { VALID: 'ok', EXPIRING: 'warn', EXPIRED: 'error', MISSING: 'error' } as const;

export default async function AccountsPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: AccountsResponse;
  let providers: { providers: Array<{ platform: string; available: boolean; reason?: string }> };
  try {
    [data, providers] = await Promise.all([
      apiFetch<AccountsResponse>('/accounts', { cookie }),
      apiFetch<typeof providers>('/oauth/providers', { cookie }),
    ]);
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403
        ? 'Sign in to manage social accounts.'
        : (err as Error).message;
    return (
      <>
        <PageHeader title="Social Accounts" />
        <div className="p-8"><ErrorPanel title="Unavailable" message={message} /></div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Social Accounts"
        description="Connect the accounts the system publishes to. Credentials are encrypted at rest and never leave the server."
      />

      <div className="space-y-6 p-8">
        <ConnectButtons providers={providers.providers} />

        {data.accounts.length === 0 ? (
          <EmptyState
            title="No accounts connected"
            description="Connect Instagram, TikTok, or a Facebook Page to begin. Instagram requires a Professional account linked to a Facebook Page."
          />
        ) : (
          <div className="space-y-4">
            {data.accounts.map((account) => (
              <div key={account.id} className="card">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink-border px-5 py-4">
                  <div className="flex items-center gap-4">
                    {account.profileImageUrl ? (
                      <img src={account.profileImageUrl} alt="" className="h-11 w-11 rounded-full object-cover" />
                    ) : (
                      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-ink-raised font-display text-sm text-bone-dim">
                        {account.username.slice(0, 2).toUpperCase()}
                      </div>
                    )}
                    <div>
                      <div className="text-sm font-medium text-bone">@{account.username}</div>
                      <div className="mt-0.5 text-[11px] uppercase tracking-wider text-bone-dim">
                        {account.platform}
                        {account.accountType && ` · ${account.accountType}`}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill tone={account.status === 'CONNECTED' ? 'ok' : 'error'}>
                      {account.status}
                    </StatusPill>
                    <StatusPill tone={TOKEN_TONE[account.tokenStatus]}>
                      Token {account.tokenStatus}
                    </StatusPill>
                  </div>
                </div>

                {/* The single most important warning on this page: an unaudited
                    TikTok client publishes privately, and the operator must know. */}
                {account.auditWarning && (
                  <div className="border-b border-ink-border bg-state-warn/5 px-5 py-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-state-warn">
                      Audit pending
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-bone-muted">{account.auditWarning}</p>
                  </div>
                )}

                {account.lastPublishError && (
                  <div className="border-b border-ink-border bg-state-error/5 px-5 py-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-state-error">
                      Last publish failed
                    </div>
                    <p className="mt-1 text-xs text-bone-muted">{account.lastPublishError}</p>
                  </div>
                )}

                <div className="grid gap-px bg-ink-border sm:grid-cols-4">
                  <Field label="Followers"><MetricValue value={account.followerCount} /></Field>
                  <Field label="Posts published">{account.postCount}</Field>
                  <Field label="Last publish">
                    {account.lastPublishAt ? new Date(account.lastPublishAt).toLocaleDateString() : '—'}
                  </Field>
                  <Field label="Token expires">
                    {account.tokenExpiresAt ? new Date(account.tokenExpiresAt).toLocaleDateString() : '—'}
                  </Field>
                </div>

                {account.capabilities && (
                  <div className="space-y-3 px-5 py-4">
                    <div className="label">What this platform&rsquo;s API allows</div>
                    <div className="flex flex-wrap gap-2">
                      <Capability on={account.capabilities.canPostCarousel} label="Carousels" />
                      <Capability on={account.capabilities.canPostVideo} label="Video / Reels" />
                      <Capability on={account.capabilities.canSchedule} label="Native scheduling" />
                      <Capability on={account.capabilities.canDelete} label="Delete post" />
                    </div>

                    {!account.capabilities.canSchedule && (
                      <Unavailable reason={account.capabilities.notes['canSchedule']} />
                    )}
                    {!account.capabilities.canDelete && (
                      <Unavailable reason={account.capabilities.notes['canDelete']} />
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-ink-soft px-5 py-3.5">
      <div className="label">{label}</div>
      <div className="mt-1 text-sm text-bone">{children}</div>
    </div>
  );
}

function Capability({ on, label }: { on: boolean; label: string }) {
  return (
    <span className={`pill ${on ? 'border-state-ok/40 text-state-ok' : 'border-ink-border text-bone-dim'}`}>
      {on ? '✓' : '✕'} {label}
    </span>
  );
}
