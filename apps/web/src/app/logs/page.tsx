import { headers } from 'next/headers';
import {
  apiFetch,
  ApiError,
  type AgentRunsResponse,
  type AuditLogResponse,
  type PublishingLogResponse,
} from '@/lib/api';
import { PageHeader, StatusPill, ErrorPanel } from '@/components/ui';

export const dynamic = 'force-dynamic';

export default async function LogsPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let agents: AgentRunsResponse;
  let publishing: PublishingLogResponse;
  // The audit log is admin-only, so a viewer legitimately gets nothing here.
  let audit: AuditLogResponse | null = null;

  try {
    [agents, publishing] = await Promise.all([
      apiFetch<AgentRunsResponse>('/logs/agents?limit=40', { cookie }),
      apiFetch<PublishingLogResponse>('/logs/publishing', { cookie }),
    ]);
    audit = await apiFetch<AuditLogResponse>('/logs/audit?limit=40', { cookie }).catch(() => null);
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403 ? 'Sign in to view logs.' : (err as Error).message;
    return (
      <>
        <PageHeader title="Logs" />
        <div className="p-8"><ErrorPanel title="Unavailable" message={message} /></div>
      </>
    );
  }

  const failedRuns = agents.runs.filter((r) => r.status === 'FAILED');

  return (
    <>
      <PageHeader
        title="Logs"
        description="What the system actually did. Every agent run, publish attempt, and privileged action."
      />

      <div className="space-y-6 p-8">
        {failedRuns.length > 0 && (
          <div className="card card-pad border-state-error/40">
            <div className="text-sm font-medium text-state-error">
              {failedRuns.length} failed agent run{failedRuns.length === 1 ? '' : 's'}
            </div>
            <div className="mt-2 space-y-1.5">
              {failedRuns.slice(0, 4).map((run) => (
                <div key={run.id} className="text-xs text-bone-muted">
                  <span className="text-bone">{run.agentName}</span>
                  {run.errors[0] && <> — {run.errors[0].message}</>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Agent runs */}
        <div className="card">
          <div className="border-b border-ink-border px-5 py-4">
            <div className="label">Agent runs</div>
          </div>
          {agents.runs.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-bone-muted">
              No agent has run yet. Use Run now in Automation to trigger one.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-ink-border">
                    <th className="px-5 py-3 text-left label">Agent</th>
                    <th className="px-5 py-3 text-left label">Status</th>
                    <th className="px-5 py-3 text-left label">Work</th>
                    <th className="px-5 py-3 text-left label">Duration</th>
                    <th className="px-5 py-3 text-left label">When</th>
                  </tr>
                </thead>
                <tbody>
                  {agents.runs.map((run) => (
                    <tr key={run.id} className="border-b border-ink-border last:border-0 align-top">
                      <td className="px-5 py-3 text-bone">{run.agentName}</td>
                      <td className="px-5 py-3">
                        <StatusPill
                          tone={
                            run.status === 'SUCCESS' ? 'ok' : run.status === 'FAILED' ? 'error' : 'idle'
                          }
                        >
                          {run.status}
                        </StatusPill>
                        {run.errors.map((error) => (
                          <div key={error.id} className="mt-1 max-w-sm text-xs text-state-error">
                            {error.errorCode}: {error.message}
                          </div>
                        ))}
                      </td>
                      <td className="px-5 py-3 text-xs text-bone-muted">
                        {run.itemsProcessed} in · {run.itemsProduced} out
                      </td>
                      <td className="px-5 py-3 text-xs text-bone-muted">
                        {run.durationMs ? `${(run.durationMs / 1000).toFixed(1)}s` : '—'}
                      </td>
                      <td className="px-5 py-3 text-xs text-bone-dim">
                        {new Date(run.startedAt).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Publishing attempts */}
        <div className="card">
          <div className="border-b border-ink-border px-5 py-4">
            <div className="label">Publishing attempts</div>
            <p className="mt-1 text-xs text-bone-dim">
              Every attempt is kept, including failures, with the platform&rsquo;s own response.
            </p>
          </div>
          {publishing.jobs.length === 0 ? (
            <p className="px-5 py-8 text-center text-sm text-bone-muted">Nothing has been published yet.</p>
          ) : (
            <div className="divide-y divide-ink-border">
              {publishing.jobs.map((job) => (
                <div key={job.id} className="px-5 py-3.5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm text-bone">
                        {job.contentPiece?.title ?? 'Untitled'}
                      </div>
                      <div className="mt-0.5 text-[11px] text-bone-dim">
                        {job.socialAccount.platform} · @{job.socialAccount.username} ·{' '}
                        {job.attemptCount} attempt{job.attemptCount === 1 ? '' : 's'}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <StatusPill
                        tone={
                          job.status === 'PUBLISHED' ? 'ok' : job.status === 'FAILED' ? 'error' : 'idle'
                        }
                      >
                        {job.status}
                      </StatusPill>
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

                  {job.lastError && (
                    <div className="mt-2 rounded border border-state-error/30 bg-state-error/5 px-3 py-2">
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-state-error">
                        {job.lastErrorCode ?? 'Error'}
                      </div>
                      <div className="mt-0.5 text-xs text-bone-muted">{job.lastError}</div>
                    </div>
                  )}

                  {job.attempts.length > 0 && (
                    <div className="mt-2 space-y-0.5">
                      {job.attempts.map((attempt) => (
                        <div key={attempt.id} className="text-[11px] text-bone-dim">
                          <span className={attempt.success ? 'text-state-ok' : 'text-state-error'}>
                            {attempt.success ? '✓' : '✕'}
                          </span>{' '}
                          #{attempt.attemptNumber} {attempt.step}
                          {attempt.errorMessage && ` — ${attempt.errorMessage}`}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Audit trail */}
        <div className="card">
          <div className="border-b border-ink-border px-5 py-4">
            <div className="label">Audit trail</div>
            <p className="mt-1 text-xs text-bone-dim">
              Immutable record of every privileged action. Administrators only.
            </p>
          </div>
          {audit === null ? (
            <p className="px-5 py-6 text-center text-sm text-bone-muted">
              The audit trail requires an administrator account.
            </p>
          ) : audit.logs.length === 0 ? (
            <p className="px-5 py-6 text-center text-sm text-bone-muted">No actions recorded yet.</p>
          ) : (
            <div className="divide-y divide-ink-border">
              {audit.logs.map((log) => (
                <div key={log.id} className="flex items-center justify-between gap-4 px-5 py-2.5">
                  <div className="min-w-0 text-sm text-bone-muted">
                    <span className="text-bone">{log.action}</span>
                    {log.subjectType && (
                      <span className="text-bone-dim"> · {log.subjectType}</span>
                    )}
                  </div>
                  <div className="shrink-0 text-[11px] text-bone-dim">
                    {log.actorType} · {new Date(log.createdAt).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
