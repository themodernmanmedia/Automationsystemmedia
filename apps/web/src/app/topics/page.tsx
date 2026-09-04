import { headers } from 'next/headers';
import { apiFetch, ApiError, type TopicsResponse } from '@/lib/api';
import { PageHeader, StatusPill, EmptyState, ErrorPanel } from '@/components/ui';

export const dynamic = 'force-dynamic';

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'error' | 'idle'> = {
  SELECTED: 'ok',
  RESEARCHED: 'ok',
  USED: 'idle',
  IN_PRODUCTION: 'warn',
  RESEARCHING: 'warn',
  DISCOVERED: 'idle',
  SCORED: 'idle',
  REJECTED: 'error',
  EXPIRED: 'error',
};

/** Explains why a topic sits where it does, so the pipeline is legible. */
const STATUS_MEANING: Record<string, string> = {
  DISCOVERED: 'Found, not yet scored',
  SCORED: 'Scored below the threshold to research',
  SELECTED: 'Scored well enough to research',
  RESEARCHING: 'Gathering sources',
  RESEARCHED: 'Sources gathered and claims verified',
  IN_PRODUCTION: 'Content being written',
  USED: 'Content produced',
  REJECTED: 'Failed fact checking, or research could not be completed',
  EXPIRED: 'Timeliness window passed',
};

export default async function TopicsPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: TopicsResponse;
  try {
    data = await apiFetch<TopicsResponse>('/topics?limit=100', { cookie });
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403 ? 'Sign in to view topics.' : (err as Error).message;
    return (
      <>
        <PageHeader title="Topics" />
        <div className="p-8"><ErrorPanel title="Unavailable" message={message} /></div>
      </>
    );
  }

  const rejected = data.topics.filter((t) => t.status === 'REJECTED').length;

  return (
    <>
      <PageHeader
        title="Topics"
        description="Everything the trend hunter has found, with the score that decides what gets researched."
      />

      <div className="space-y-6 p-8">
        {rejected > 0 && (
          <div className="card card-pad">
            <div className="label">Rejected topics</div>
            <p className="mt-2 text-sm leading-relaxed text-bone-muted">
              {rejected} topic{rejected === 1 ? '' : 's'} {rejected === 1 ? 'was' : 'were'} rejected.
              The usual cause is fact checking: if too few claims could be verified against the
              retrieved sources, the topic is dropped rather than written up. Thin or unfetchable
              sources are the most common reason.
            </p>
          </div>
        )}

        {data.topics.length === 0 ? (
          <EmptyState
            title="No topics yet"
            description="The trend hunter populates this from the RSS feeds and search providers you configure. It only ever selects from items actually retrieved — it never invents a story."
          />
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-ink-border">
                    <th className="px-5 py-3 text-left label">Topic</th>
                    <th className="px-5 py-3 text-left label">Category</th>
                    <th className="px-5 py-3 text-left label">Score</th>
                    <th className="px-5 py-3 text-left label">Evidence</th>
                    <th className="px-5 py-3 text-left label">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.topics.map((topic) => (
                    <tr key={topic.id} className="border-b border-ink-border last:border-0 align-top">
                      <td className="max-w-md px-5 py-3.5">
                        <div className="flex items-start gap-2">
                          <div className="min-w-0">
                            <div className="truncate text-bone">{topic.title}</div>
                            <div className="mt-0.5 line-clamp-2 text-xs text-bone-dim">{topic.summary}</div>
                            {topic.discoveryUrl && (
                              <a
                                href={topic.discoveryUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="mt-1 inline-block text-[11px] text-gold hover:underline"
                              >
                                {topic.discoverySource}
                              </a>
                            )}
                          </div>
                          {topic.isBreakingNews && (
                            <span className="pill shrink-0 border-state-warn/40 text-state-warn">
                              Breaking
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-bone-muted">{topic.category}</td>
                      <td className="px-5 py-3.5">
                        <span
                          className={
                            (topic.compositeScore ?? 0) >= 60
                              ? 'font-display text-lg text-gold'
                              : 'font-display text-lg text-bone-dim'
                          }
                        >
                          {topic.compositeScore?.toFixed(0) ?? '—'}
                        </span>
                        {topic.compositeScore !== null && topic.compositeScore < 60 && (
                          <div className="text-[11px] text-bone-dim">below threshold</div>
                        )}
                      </td>
                      <td className="px-5 py-3.5 text-xs text-bone-muted">
                        <div>{topic._count.sources} sources</div>
                        <div>{topic._count.claims} claims</div>
                        {topic._count.contentPieces > 0 && (
                          <div className="text-state-ok">{topic._count.contentPieces} produced</div>
                        )}
                      </td>
                      <td className="px-5 py-3.5">
                        <StatusPill tone={STATUS_TONE[topic.status] ?? 'idle'}>{topic.status}</StatusPill>
                        <div className="mt-1 max-w-[14rem] text-[11px] leading-snug text-bone-dim">
                          {STATUS_MEANING[topic.status]}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <p className="text-xs leading-relaxed text-bone-dim">
          Scores rank topics against each other. A topic scoring 60 or above is researched; below
          that it is kept but not acted on, since research costs real money.
        </p>
      </div>
    </>
  );
}
