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

  async function refresh() {
    setData(await clientFetch<AutomationResponse>('/automation'));
  }

  function act(fn: () => Promise<unknown>) {
    setError(null);
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
