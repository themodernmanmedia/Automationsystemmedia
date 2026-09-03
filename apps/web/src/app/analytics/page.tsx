import { headers } from 'next/headers';
import { apiFetch, ApiError } from '@/lib/api';
import { PageHeader, Stat, MetricValue, EmptyState, ErrorPanel } from '@/components/ui';

export const dynamic = 'force-dynamic';

interface AnalyticsSummary {
  totals: Record<string, number | null>;
  byPlatform: Array<{ platform: string; views: number | null; reach: number | null; engagementRate: number | null; posts: number }>;
  unavailable: Record<string, string[]>;
  topContent: Array<{
    id: string;
    engagementRate: number | null;
    views: number | null;
    publishingJob: { contentPiece: { id: string; title: string; format: string; category: string } | null } | null;
  }>;
}

export default async function AnalyticsPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: AnalyticsSummary;
  try {
    data = await apiFetch<AnalyticsSummary>('/analytics/summary?days=30', { cookie });
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403
        ? 'Sign in to view analytics.'
        : (err as Error).message;
    return (
      <>
        <PageHeader title="Analytics" />
        <div className="p-8"><ErrorPanel title="Unavailable" message={message} /></div>
      </>
    );
  }

  const hasData = data.byPlatform.length > 0;

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Collected from each platform's official API over the last 30 days."
      />

      <div className="space-y-6 p-8">
        {!hasData ? (
          <EmptyState
            title="No analytics collected yet"
            description="Analytics are collected from connected accounts after posts have been live long enough for the platforms to report on them. Nothing is estimated or filled in."
          />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <Stat label="Views" value={<MetricValue value={data.totals['views']} />} />
              <Stat label="Reach" value={<MetricValue value={data.totals['reach']} />} />
              <Stat label="Saves" value={<MetricValue value={data.totals['saves']} />} />
              <Stat label="Shares" value={<MetricValue value={data.totals['shares']} />} />
            </div>

            <div className="card">
              <div className="border-b border-ink-border px-5 py-4">
                <div className="label">By platform</div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-ink-border">
                      <th className="px-5 py-3 text-left label">Platform</th>
                      <th className="px-5 py-3 text-left label">Posts</th>
                      <th className="px-5 py-3 text-left label">Views</th>
                      <th className="px-5 py-3 text-left label">Reach</th>
                      <th className="px-5 py-3 text-left label">Engagement</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.byPlatform.map((row) => (
                      <tr key={row.platform} className="border-b border-ink-border last:border-0">
                        <td className="px-5 py-3.5 text-bone">{row.platform}</td>
                        <td className="px-5 py-3.5 text-bone-muted">{row.posts}</td>
                        <td className="px-5 py-3.5 text-bone-muted"><MetricValue value={row.views} /></td>
                        <td className="px-5 py-3.5 text-bone-muted"><MetricValue value={row.reach} /></td>
                        <td className="px-5 py-3.5 text-bone-muted">
                          <MetricValue value={row.engagementRate} format="percent" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {Object.keys(data.unavailable).length > 0 && (
              <div className="card card-pad">
                <div className="label">Metrics these platforms do not report</div>
                <p className="mt-2 text-xs leading-relaxed text-bone-muted">
                  These are absent from the platform APIs, not zero. They are stored as unavailable
                  so they cannot skew the learning engine.
                </p>
                <div className="mt-3 space-y-2">
                  {Object.entries(data.unavailable).map(([platform, metrics]) => (
                    <div key={platform} className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium uppercase tracking-wider text-bone-dim">
                        {platform}
                      </span>
                      {metrics.map((metric) => (
                        <span key={metric} className="pill border-ink-border text-bone-dim">{metric}</span>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {data.topContent.length > 0 && (
              <div className="card">
                <div className="border-b border-ink-border px-5 py-4">
                  <div className="label">Best performing content</div>
                </div>
                <div className="divide-y divide-ink-border">
                  {data.topContent.map((row) => (
                    <div key={row.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
                      <div className="min-w-0">
                        <div className="truncate text-sm text-bone">
                          {row.publishingJob?.contentPiece?.title ?? 'Unknown'}
                        </div>
                        <div className="text-xs text-bone-dim">
                          {row.publishingJob?.contentPiece?.format} · {row.publishingJob?.contentPiece?.category}
                        </div>
                      </div>
                      <div className="shrink-0 text-sm text-gold">
                        <MetricValue value={row.engagementRate} format="percent" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
