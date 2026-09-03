import { headers } from 'next/headers';
import { apiFetch, ApiError } from '@/lib/api';
import { PageHeader, StatusPill, EmptyState, ErrorPanel } from '@/components/ui';

export const dynamic = 'force-dynamic';

interface ContentItem {
  id: string;
  title: string;
  hook: string;
  format: string;
  status: string;
  category: string;
  createdAt: string;
  viralPotentialScore: number | null;
  qualityScore: number | null;
  flagReason: string | null;
  topic: { id: string; title: string; compositeScore: number | null } | null;
  carousel: { slideCount: number } | null;
  reel: { durationSec: number | null; renderStatus: string } | null;
  publishingJobs: Array<{ id: string; platform: string; status: string; scheduledAt: string; platformUrl: string | null }>;
}

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'error' | 'idle'> = {
  PUBLISHED: 'ok', LEARNED: 'ok', APPROVED: 'ok', ANALYZING: 'ok',
  SCHEDULED: 'idle', QA: 'idle', WRITING: 'idle', DESIGNING: 'idle',
  RESEARCHING: 'idle', RESEARCHED: 'idle', DISCOVERED: 'idle', PUBLISHING: 'idle',
  FLAGGED: 'warn', FAILED: 'error', ARCHIVED: 'idle',
};

export default async function ContentPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: { items: ContentItem[] };
  try {
    data = await apiFetch<{ items: ContentItem[] }>('/content?limit=50', { cookie });
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403
        ? 'Sign in to view content.'
        : (err as Error).message;
    return (
      <>
        <PageHeader title="Content" />
        <div className="p-8"><ErrorPanel title="Unavailable" message={message} /></div>
      </>
    );
  }

  const flagged = data.items.filter((i) => i.status === 'FLAGGED');

  return (
    <>
      <PageHeader
        title="Content"
        description="Everything the pipeline has produced, with the lifecycle stage each piece has reached."
      />

      <div className="space-y-6 p-8">
        {flagged.length > 0 && (
          <div className="card border-state-warn/40">
            <div className="border-b border-ink-border px-5 py-4">
              <div className="text-sm font-medium text-state-warn">
                Exception queue · {flagged.length} item{flagged.length === 1 ? '' : 's'}
              </div>
              <p className="mt-1 text-xs text-bone-muted">
                Autonomous mode declined to publish these. Each one names the gate that stopped it.
              </p>
            </div>
            <div className="divide-y divide-ink-border">
              {flagged.map((item) => (
                <div key={item.id} className="px-5 py-3.5">
                  <div className="text-sm text-bone">{item.title}</div>
                  {item.flagReason && (
                    <div className="mt-1 text-xs text-state-warn">{item.flagReason}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {data.items.length === 0 ? (
          <EmptyState
            title="No content yet"
            description="The pipeline produces content once an LLM provider and a research source are configured and autonomous mode is enabled. Nothing is fabricated to fill this space."
          />
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-ink-border">
                    <th className="px-5 py-3 text-left label">Title</th>
                    <th className="px-5 py-3 text-left label">Format</th>
                    <th className="px-5 py-3 text-left label">Category</th>
                    <th className="px-5 py-3 text-left label">Status</th>
                    <th className="px-5 py-3 text-left label">Score</th>
                    <th className="px-5 py-3 text-left label">Targets</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => (
                    <tr key={item.id} className="border-b border-ink-border last:border-0">
                      <td className="max-w-xs px-5 py-3.5">
                        <div className="truncate text-bone">{item.title}</div>
                        <div className="mt-0.5 truncate text-xs text-bone-dim">{item.hook}</div>
                      </td>
                      <td className="px-5 py-3.5 text-bone-muted">
                        {item.format}
                        {item.carousel && <span className="text-bone-dim"> · {item.carousel.slideCount} slides</span>}
                        {item.reel?.durationSec && <span className="text-bone-dim"> · {item.reel.durationSec.toFixed(0)}s</span>}
                      </td>
                      <td className="px-5 py-3.5 text-bone-muted">{item.category}</td>
                      <td className="px-5 py-3.5">
                        <StatusPill tone={STATUS_TONE[item.status] ?? 'idle'}>{item.status}</StatusPill>
                      </td>
                      <td className="px-5 py-3.5 text-bone-muted">
                        {item.viralPotentialScore?.toFixed(0) ?? '—'}
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex flex-wrap gap-1.5">
                          {item.publishingJobs.length === 0 ? (
                            <span className="text-xs text-bone-dim">—</span>
                          ) : (
                            item.publishingJobs.map((job) => (
                              <span key={job.id} className="pill border-ink-border text-bone-dim">
                                {job.platform} · {job.status}
                              </span>
                            ))
                          )}
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
          Ranking scores order the queue. They are not predictions of performance.
        </p>
      </div>
    </>
  );
}
