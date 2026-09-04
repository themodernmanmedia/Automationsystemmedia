'use client';

import { useState, useTransition } from 'react';
import { clientFetch, type AutomationResponse } from '@/lib/api';
import { StatusPill, Stat } from '@/components/ui';

const QUEUE_TONE = {
  CRITICAL: 'error',
  LOW: 'warn',
  HEALTHY: 'ok',
  FULL: 'ok',
} as const;

const AGENT_LABELS: Record<string, string> = {
  trendHunter: 'Trend Hunter',
  topicScorer: 'Topic Scorer',
  researcher: 'Researcher',
  factChecker: 'Fact Checker',
  strategist: 'Content Strategist',
  hookEngine: 'Hook Engine',
  carouselWriter: 'Carousel Writer',
  carouselDesigner: 'Carousel Designer',
  reelWriter: 'Reel Writer',
  reelProducer: 'Reel Producer',
  mediaSourcing: 'Media Sourcing',
  qualityControl: 'Quality Control',
  publisher: 'Publisher',
  analytics: 'Analytics',
  learningEngine: 'Learning Engine',
};

export function AutomationControls({ initial }: { initial: AutomationResponse }) {
  const [data, setData] = useState(initial);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function refresh() {
    setData(await clientFetch<AutomationResponse>('/automation'));
  }

  function act(fn: () => Promise<unknown>) {
    setError(null);
    setNotice(null);
    startTransition(async () => {
      try {
        const result = (await fn()) as { error?: string };
        // The API refuses some actions with an explanation rather than an
        // error status — surface that text verbatim.
        if (result?.error) setError(result.error);
        await refresh();
      } catch (err) {
        setError((err as Error).message);
      }
    });
  }

  const { state, queue, agents, integrations, integrationErrors } = data;
  const llmReady = integrations['llm'] === true;

  return (
    <div className="space-y-6">
      {error && (
        <div className="card card-pad border-state-error/40">
          <div className="text-sm text-state-error">{error}</div>
        </div>
      )}
      {notice && (
        <div className="card card-pad border-state-ok/40">
          <div className="text-sm text-state-ok">{notice}</div>
        </div>
      )}

      {/* Master controls */}
      <div className="card">
        <div className="flex items-center justify-between border-b border-ink-border px-5 py-4">
          <div className="label">Master controls</div>
          <StatusPill tone={state.killSwitch ? 'error' : state.autonomousMode ? 'ok' : 'idle'}>
            {state.killSwitch ? 'Halted' : state.autonomousMode ? 'Autonomous' : 'Manual'}
          </StatusPill>
        </div>

        <div className="grid gap-4 p-5 md:grid-cols-2">
          <div className="rounded-md border border-ink-border p-4">
            <div className="text-sm font-medium text-bone">Autonomous mode</div>
            <p className="mt-1 text-xs leading-relaxed text-bone-muted">
              The system discovers, researches, writes, checks, schedules, and publishes without
              asking. Low-risk content ships; anything uncertain goes to the exception queue.
            </p>
            {!llmReady && (
              <p className="mt-2 text-xs text-state-warn">
                {integrationErrors['llm'] ?? 'An LLM provider must be configured first.'}
              </p>
            )}
            <button
              className={state.autonomousMode ? 'btn-ghost mt-3' : 'btn-primary mt-3'}
              disabled={pending || (!state.autonomousMode && !llmReady) || state.killSwitch}
              onClick={() =>
                act(() =>
                  clientFetch('/automation/autonomous', {
                    method: 'POST',
                    body: JSON.stringify({ enabled: !state.autonomousMode }),
                  }),
                )
              }
            >
              {state.autonomousMode ? 'Disable autonomous mode' : 'Enable autonomous mode'}
            </button>
          </div>

          <div className="rounded-md border border-ink-border p-4">
            <div className="text-sm font-medium text-bone">Publishing</div>
            <p className="mt-1 text-xs leading-relaxed text-bone-muted">
              Pausing stops posts going out while the rest of the pipeline keeps running. Content
              continues to be produced and queued.
            </p>
            <button
              className="btn-ghost mt-3"
              disabled={pending}
              onClick={() =>
                act(() =>
                  clientFetch('/automation/publishing', {
                    method: 'POST',
                    body: JSON.stringify({ paused: !state.publishingPaused }),
                  }),
                )
              }
            >
              {state.publishingPaused ? 'Resume publishing' : 'Pause publishing'}
            </button>
          </div>
        </div>

        <div className="border-t border-ink-border bg-ink/40 p-5">
          <div className="text-sm font-medium text-state-error">Emergency controls</div>
          <p className="mt-1 text-xs leading-relaxed text-bone-muted">
            The kill switch halts everything immediately and is checked again right before every
            publish, so work already in flight stops too.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              className={state.killSwitch ? 'btn-primary' : 'btn-danger'}
              disabled={pending}
              onClick={() =>
                act(() =>
                  clientFetch('/automation/kill', {
                    method: 'POST',
                    body: JSON.stringify({ engaged: !state.killSwitch }),
                  }),
                )
              }
            >
              {state.killSwitch ? 'Release kill switch' : 'Stop all automation'}
            </button>
            <button
              className="btn-danger"
              disabled={pending}
              onClick={() => {
                if (!confirm('Cancel every queued and scheduled post? This cannot be undone.')) return;
                act(() => clientFetch('/automation/queue/clear', { method: 'POST', body: '{}' }));
              }}
            >
              Clear queue
            </button>
          </div>
        </div>
      </div>

      {/* Run now */}
      <div className="card">
        <div className="border-b border-ink-border px-5 py-4">
          <div className="label">Run now</div>
          <p className="mt-1 text-xs leading-relaxed text-bone-dim">
            Runs a stage immediately, using the same code path the scheduler uses. Use this to see
            what the system produces before trusting it to run unattended.
          </p>
        </div>
        <div className="grid gap-px bg-ink-border sm:grid-cols-2 lg:grid-cols-4">
          {[
            { job: 'tick', label: 'Discover & generate', hint: 'Scan trends, score, research, write' },
            { job: 'render', label: 'Render Reels', hint: 'Voice and compose queued Reels' },
            { job: 'analytics', label: 'Collect analytics', hint: 'Pull metrics for published posts' },
            { job: 'snapshot', label: 'Snapshot accounts', hint: 'Record follower counts' },
          ].map((item) => (
            <div key={item.job} className="bg-ink-soft p-5">
              <div className="text-sm font-medium text-bone">{item.label}</div>
              <p className="mt-1 min-h-[2.25rem] text-xs leading-relaxed text-bone-muted">{item.hint}</p>
              <button
                className="btn-ghost mt-2 w-full"
                disabled={pending || state.killSwitch || (item.job === 'tick' && !llmReady)}
                onClick={() =>
                  act(async () => {
                    await clientFetch(`/automation/run/${item.job}`, { method: 'POST', body: '{}' });
                    setNotice(`Queued "${item.label}". Watch the agent list below and the Content page for results.`);
                  })
                }
              >
                Run now
              </button>
            </div>
          ))}
        </div>
        <div className="border-t border-ink-border px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-bone">Retry failed posts</div>
              <p className="mt-1 text-xs leading-relaxed text-bone-muted">
                Requeues failed publishing jobs. Authentication failures are skipped — the token is
                dead, so retrying only consumes platform rate limit.
              </p>
            </div>
            <button
              className="btn-ghost shrink-0"
              disabled={pending || state.killSwitch}
              onClick={() =>
                act(async () => {
                  const result = (await clientFetch('/automation/publishing/retry', {
                    method: 'POST',
                    body: '{}',
                  })) as { requeued: number; skipped: Array<{ account: string; reason: string }> };
                  const skippedNote = result.skipped.length
                    ? ` ${result.skipped.length} skipped — reconnect: ${[...new Set(result.skipped.map((s) => s.account))].join(', ')}.`
                    : '';
                  setNotice(`Requeued ${result.requeued} job(s).${skippedNote}`);
                })
              }
            >
              Retry failed
            </button>
          </div>
        </div>
      </div>

      {/* Queue health */}
      <div className="grid gap-4 md:grid-cols-4">
        <Stat
          label="Queue depth"
          value={`${queue.hoursOfContent}h`}
          tone={QUEUE_TONE[queue.status]}
          hint={`Target ${state.targetQueueHours}h · minimum ${state.minQueueHours}h`}
        />
        <Stat label="Scheduled posts" value={queue.scheduledCount} />
        <Stat
          label="Queue status"
          value={queue.status}
          tone={QUEUE_TONE[queue.status]}
        />
        <Stat
          label="Posts needed"
          value={queue.postsNeeded}
          hint={queue.shouldGenerate ? 'Generation will run' : 'Backlog is sufficient'}
        />
      </div>

      {/* Agents */}
      <div className="card">
        <div className="border-b border-ink-border px-5 py-4">
          <div className="label">Agents</div>
          <p className="mt-1 text-xs text-bone-dim">
            Status is derived from real run records over the last 24 hours.
          </p>
        </div>
        <div className="divide-y divide-ink-border">
          {agents.map((agent) => (
            <div key={agent.key} className="flex items-center justify-between gap-4 px-5 py-3">
              <div className="min-w-0">
                <div className="text-sm text-bone">{AGENT_LABELS[agent.key] ?? agent.key}</div>
                <div className="mt-0.5 text-xs text-bone-dim">
                  {agent.runsLast24h} run{agent.runsLast24h === 1 ? '' : 's'} in 24h
                  {agent.failuresLast24h > 0 && (
                    <span className="text-state-error"> · {agent.failuresLast24h} failed</span>
                  )}
                  {agent.lastRunAt && ` · last ${new Date(agent.lastRunAt).toLocaleString()}`}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <StatusPill
                  tone={
                    agent.status === 'ERROR' ? 'error'
                    : agent.status === 'RUNNING' ? 'ok'
                    : agent.status === 'PAUSED' ? 'warn'
                    : 'idle'
                  }
                >
                  {agent.status}
                </StatusPill>
                <button
                  className="btn-ghost !px-2.5 !py-1 text-xs"
                  disabled={pending}
                  onClick={() =>
                    act(() =>
                      clientFetch(`/automation/agents/${agent.key}`, {
                        method: 'POST',
                        body: JSON.stringify({ enabled: !agent.enabled }),
                      }),
                    )
                  }
                >
                  {agent.enabled ? 'Disable' : 'Enable'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
