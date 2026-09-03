import { headers } from 'next/headers';
import Link from 'next/link';
import { apiFetch, ApiError, type Overview } from '@/lib/api';
import { PageHeader, Stat, StatusPill, MetricValue, ErrorPanel, EmptyState } from '@/components/ui';

export const dynamic = 'force-dynamic';

/** Acronyms and brand names that CSS `capitalize` would render wrongly. */
const INTEGRATION_LABELS: Record<string, string> = {
  storage: 'Storage',
  llm: 'LLM',
  image: 'Image generation',
  voice: 'Voice',
  search: 'Research',
  meta: 'Meta (Instagram + Facebook)',
  tiktok: 'TikTok',
};

export default async function OverviewPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: Overview;
  try {
    data = await apiFetch<Overview>('/overview', { cookie });
  } catch (err) {
    if (err instanceof ApiError && err.status === 403) {
      return (
        <>
          <PageHeader title="Overview" />
          <div className="p-8">
            <EmptyState
              title="Sign in required"
              description="Sign in to view the operating system."
              action={<Link href="/login" className="btn-primary">Go to sign in</Link>}
            />
          </div>
        </>
      );
    }
    return (
      <>
        <PageHeader title="Overview" />
        <div className="p-8">
          <ErrorPanel
            title="Could not reach the API"
            message={`${(err as Error).message}. Check that the API server is running on the configured port.`}
          />
        </div>
      </>
    );
  }

  const { automation, today } = data;
  const modeTone = automation.killSwitch ? 'error' : automation.autonomousMode ? 'ok' : 'idle';
  const modeLabel = automation.killSwitch
    ? 'Halted'
    : automation.autonomousMode
      ? 'Autonomous'
      : 'Manual';

  const unconfigured = Object.entries(data.integrations)
    .filter(([, on]) => !on)
    .map(([key]) => key);

  return (
    <>
      <PageHeader
        title="Overview"
        description="Today's operation at a glance."
        actions={<StatusPill tone={modeTone}>{modeLabel}</StatusPill>}
      />

      <div className="space-y-6 p-8">
        {automation.killSwitch && (
          <div className="card card-pad border-state-error/50 bg-state-error/5">
            <div className="font-medium text-state-error">Kill switch engaged</div>
            <p className="mt-1 text-sm text-bone-muted">
              All automation is halted. Nothing will be published until it is released in{' '}
              <Link href="/automation" className="text-gold underline">Automation</Link>.
            </p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Published today" value={today.published} />
          <Stat label="Queued" value={today.queued} hint="Scheduled and waiting" />
          <Stat
            label="Needs review"
            value={today.flagged}
            tone={today.flagged > 0 ? 'warn' : 'default'}
            hint="Exception queue"
          />
          <Stat
            label="Failed (7d)"
            value={today.failed}
            tone={today.failed > 0 ? 'error' : 'default'}
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="card lg:col-span-2">
            <div className="border-b border-ink-border px-5 py-4">
              <div className="label">Reach and engagement · last 7 days</div>
            </div>
            <div className="grid grid-cols-2 gap-px bg-ink-border sm:grid-cols-4">
              {(['views', 'reach', 'saves', 'shares'] as const).map((key) => (
                <div key={key} className="bg-ink-soft p-5">
                  <div className="label capitalize">{key}</div>
                  <div className="mt-2 font-display text-2xl tracking-tightest text-bone">
                    <MetricValue value={data.weekAnalytics[key]} />
                  </div>
                </div>
              ))}
            </div>
            <p className="border-t border-ink-border px-5 py-3 text-xs text-bone-dim">
              Metrics shown as &ldquo;not reported&rdquo; are ones the platform&rsquo;s API does not
              return. They are never recorded as zero.
            </p>
          </div>

          <div className="card">
            <div className="border-b border-ink-border px-5 py-4">
              <div className="label">Connected accounts</div>
            </div>
            {data.accounts.length === 0 ? (
              <div className="px-5 py-8 text-center">
                <p className="text-sm text-bone-muted">No accounts connected yet.</p>
                <Link href="/accounts" className="btn-ghost mt-4">Connect an account</Link>
              </div>
            ) : (
              <div className="divide-y divide-ink-border">
                {data.accounts.map((account) => (
                  <div key={`${account.platform}-${account.username}`} className="flex items-center justify-between px-5 py-3.5">
                    <div>
                      <div className="text-sm text-bone">@{account.username}</div>
                      <div className="text-[11px] uppercase tracking-wider text-bone-dim">{account.platform}</div>
                    </div>
                    <div className="text-sm text-bone-muted">
                      <MetricValue value={account.followerCount} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="card">
            <div className="border-b border-ink-border px-5 py-4">
              <div className="label">Top scored topics</div>
            </div>
            {data.trendingTopics.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-bone-muted">
                No scored topics yet. The trend hunter populates this once research providers are configured.
              </p>
            ) : (
              <div className="divide-y divide-ink-border">
                {data.trendingTopics.map((topic) => (
                  <div key={topic.id} className="flex items-start justify-between gap-4 px-5 py-3.5">
                    <div className="min-w-0">
                      <div className="truncate text-sm text-bone">{topic.title}</div>
                      <div className="mt-1 flex items-center gap-2">
                        <span className="text-[11px] uppercase tracking-wider text-bone-dim">{topic.category}</span>
                        {topic.isBreakingNews && (
                          <span className="pill border-state-warn/40 text-state-warn">Breaking</span>
                        )}
                      </div>
                    </div>
                    <div className="shrink-0 font-display text-lg text-gold">
                      {topic.compositeScore?.toFixed(0) ?? '—'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div className="border-b border-ink-border px-5 py-4">
              <div className="label">Integration status</div>
            </div>
            <div className="grid grid-cols-2 gap-px bg-ink-border">
              {Object.entries(data.integrations).map(([key, configured]) => (
                <div key={key} className="flex items-center justify-between bg-ink-soft px-5 py-3">
                  <span className="text-sm text-bone-muted">{INTEGRATION_LABELS[key] ?? key}</span>
                  <StatusPill tone={configured ? 'ok' : 'idle'}>
                    {configured ? 'Ready' : 'Not set'}
                  </StatusPill>
                </div>
              ))}
            </div>
            {unconfigured.length > 0 && (
              <p className="border-t border-ink-border px-5 py-3 text-xs leading-relaxed text-bone-dim">
                {unconfigured.length} integration{unconfigured.length === 1 ? '' : 's'} not configured.
                Features that depend on them are disabled rather than hidden — see Automation for
                the exact reason.
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
