import { headers } from 'next/headers';
import { apiFetch, ApiError, type ExperimentsResponse } from '@/lib/api';
import { PageHeader, StatusPill, EmptyState, ErrorPanel } from '@/components/ui';
import { NewExperiment } from './new-experiment';

export const dynamic = 'force-dynamic';

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'error' | 'idle'> = {
  RUNNING: 'ok',
  COMPLETE: 'idle',
  DRAFT: 'idle',
  ABANDONED: 'error',
};

export default async function ExperimentsPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: ExperimentsResponse;
  try {
    data = await apiFetch<ExperimentsResponse>('/experiments', { cookie });
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403
        ? 'Sign in to view experiments.'
        : (err as Error).message;
    return (
      <>
        <PageHeader title="Experiments" />
        <div className="p-8"><ErrorPanel title="Unavailable" message={message} /></div>
      </>
    );
  }

  const running = data.experiments.find((e) => e.status === 'RUNNING');

  return (
    <>
      <PageHeader
        title="Experiments"
        description="A/B tests on one variable at a time. Results are only acted on when the statistics support them."
      />

      <div className="space-y-6 p-8">
        <div className="card card-pad">
          <div className="label">How these are judged</div>
          <p className="mt-2 text-sm leading-relaxed text-bone-muted">
            Each experiment changes exactly one variable, because changing several makes the result
            uninterpretable. A conclusion needs every arm to reach its sample floor and then to
            separate at 95% confidence on a two-sided Welch&rsquo;s t-test. When the arms do not
            separate the verdict is <span className="text-bone">inconclusive</span> — recorded as a
            real result, and deliberately not acted on. At these volumes, adopting whichever arm
            happened to lead is how noise gets baked into strategy.
          </p>
        </div>

        <NewExperiment variables={data.testableVariables} hasRunning={Boolean(running)} />

        {data.experiments.length === 0 ? (
          <EmptyState
            title="No experiments yet"
            description="Create one to test a hook style, caption length, CTA, or posting time. Content generated while it runs is assigned to an arm automatically."
          />
        ) : (
          <div className="space-y-4">
            {data.experiments.map((experiment) => (
              <div key={experiment.id} className="card">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-ink-border px-5 py-4">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-bone">{experiment.name}</div>
                    <p className="mt-1 max-w-2xl text-xs leading-relaxed text-bone-muted">
                      {experiment.hypothesis}
                    </p>
                    <div className="mt-1.5 text-[11px] uppercase tracking-wider text-bone-dim">
                      testing {experiment.variable} · {experiment._count.contentPieces} pieces assigned
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {experiment.winner && (
                      <span className="pill border-state-ok/40 text-state-ok">
                        winner: {experiment.winner}
                      </span>
                    )}
                    <StatusPill tone={STATUS_TONE[experiment.status] ?? 'idle'}>
                      {experiment.status}
                    </StatusPill>
                  </div>
                </div>

                {/* Per-arm results */}
                <div className="grid gap-px bg-ink-border sm:grid-cols-2 lg:grid-cols-4">
                  {experiment.variants.map((variant) => {
                    const stats = experiment.results?.variants.find((v) => v.key === variant.key);
                    const needed = experiment.results?.shortfall?.[variant.key] ?? null;
                    const isWinner = experiment.winner === variant.key;
                    return (
                      <div key={variant.key} className="bg-ink-soft p-4">
                        <div className="flex items-center justify-between">
                          <span className={`text-sm ${isWinner ? 'text-state-ok' : 'text-bone'}`}>
                            {variant.key}
                          </span>
                          {isWinner && <span className="text-xs text-state-ok">✓</span>}
                        </div>
                        <p className="mt-1 min-h-[2rem] text-xs leading-snug text-bone-dim">
                          {variant.description}
                        </p>
                        {stats ? (
                          <div className="mt-2 space-y-0.5 text-xs text-bone-muted">
                            <div>
                              <span className="text-bone-dim">n=</span>
                              {stats.sampleSize}
                              {needed ? <span className="text-state-warn"> (+{needed} needed)</span> : null}
                            </div>
                            <div>
                              <span className="text-bone-dim">mean </span>
                              <span className="font-mono">{stats.mean.toFixed(2)}</span>
                            </div>
                            <div className="text-bone-dim">± {stats.stdDev.toFixed(2)} sd</div>
                          </div>
                        ) : (
                          <div className="mt-2 text-xs text-bone-dim">no data yet</div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {experiment.conclusion && (
                  <div className="border-t border-ink-border px-5 py-3.5">
                    <div className="label">
                      {experiment.results?.verdict === 'WINNER'
                        ? 'Conclusion'
                        : experiment.results?.verdict === 'INCONCLUSIVE'
                          ? 'Inconclusive'
                          : 'Progress'}
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-bone-muted">
                      {experiment.conclusion}
                    </p>
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
