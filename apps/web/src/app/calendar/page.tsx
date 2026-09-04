import { headers } from 'next/headers';
import { apiFetch, ApiError, type CalendarResponse } from '@/lib/api';
import { PageHeader, StatusPill, EmptyState, ErrorPanel } from '@/components/ui';

export const dynamic = 'force-dynamic';

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'error' | 'idle'> = {
  PUBLISHED: 'ok',
  SCHEDULED: 'idle',
  QUEUED: 'idle',
  PUBLISHING: 'warn',
  FAILED: 'error',
  BLOCKED: 'error',
};

export default async function CalendarPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: CalendarResponse;
  try {
    data = await apiFetch<CalendarResponse>('/calendar', { cookie });
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403
        ? 'Sign in to view the calendar.'
        : (err as Error).message;
    return (
      <>
        <PageHeader title="Calendar" />
        <div className="p-8"><ErrorPanel title="Unavailable" message={message} /></div>
      </>
    );
  }

  // Group by UTC day. All scheduling in this system is UTC, so presenting local
  // days here would misrepresent when a post actually goes out.
  const byDay = new Map<string, CalendarResponse['jobs']>();
  for (const job of data.jobs) {
    const day = job.scheduledAt.slice(0, 10);
    byDay.set(day, [...(byDay.get(day) ?? []), job]);
  }
  const days = [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b));
  const today = new Date().toISOString().slice(0, 10);

  const selfTimed = data.jobs.filter(
    (j) => j.scheduleStrategy === 'SELF_TIMED' && (j.status === 'SCHEDULED' || j.status === 'QUEUED'),
  ).length;

  return (
    <>
      <PageHeader
        title="Calendar"
        description="Everything landing in the next two weeks, and the past week for context."
      />

      <div className="space-y-6 p-8">
        {selfTimed > 0 && (
          <div className="card card-pad">
            <div className="label">Worker dependency</div>
            <p className="mt-2 text-sm leading-relaxed text-bone-muted">
              {selfTimed} upcoming post{selfTimed === 1 ? '' : 's'} {selfTimed === 1 ? 'is' : 'are'}{' '}
              <span className="text-bone">self-timed</span>. Instagram and TikTok accept no future
              timestamp, so this system publishes them itself — the worker must be running at those
              moments. Facebook posts are held by Facebook and are unaffected.
            </p>
          </div>
        )}

        {days.length === 0 ? (
          <EmptyState
            title="Nothing scheduled"
            description="Scheduled and published posts appear here. The autonomous loop fills the calendar once content passes quality control, or you can schedule a piece manually from Content."
          />
        ) : (
          <div className="space-y-4">
            {days.map(([day, jobs]) => (
              <div key={day} className="card">
                <div className="flex items-center justify-between border-b border-ink-border px-5 py-3">
                  <div className="flex items-baseline gap-3">
                    <span className="font-display text-lg tracking-tightest text-bone">
                      {new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, {
                        weekday: 'long',
                        month: 'short',
                        day: 'numeric',
                        timeZone: 'UTC',
                      })}
                    </span>
                    {day === today && <span className="pill border-gold/40 text-gold">Today</span>}
                  </div>
                  <span className="text-xs text-bone-dim">
                    {jobs.length} post{jobs.length === 1 ? '' : 's'}
                  </span>
                </div>

                <div className="divide-y divide-ink-border">
                  {jobs.map((job) => (
                    <div key={job.id} className="flex items-start gap-4 px-5 py-3.5">
                      <div className="w-16 shrink-0 pt-0.5 font-mono text-sm text-bone-muted">
                        {job.scheduledAt.slice(11, 16)}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm text-bone">
                          {job.content?.title ?? 'Untitled'}
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-bone-dim">
                          <span className="uppercase tracking-wider">{job.platform}</span>
                          <span>@{job.username}</span>
                          {job.content && <span>{job.content.format}</span>}
                          {job.scheduleStrategy === 'DELEGATED' && (
                            <span className="pill border-ink-border text-bone-dim">
                              held by platform
                            </span>
                          )}
                        </div>
                        {job.lastError && (
                          <div className="mt-1.5 text-xs text-state-error">{job.lastError}</div>
                        )}
                      </div>

                      <div className="flex shrink-0 items-center gap-2">
                        <StatusPill tone={STATUS_TONE[job.status] ?? 'idle'}>{job.status}</StatusPill>
                        {job.platformUrl && (
                          <a
                            href={job.platformUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-gold hover:underline"
                          >
                            View
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        <p className="text-xs text-bone-dim">All times are UTC, which is how the scheduler stores them.</p>
      </div>
    </>
  );
}
