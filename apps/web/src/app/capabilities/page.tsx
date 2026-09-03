import { headers } from 'next/headers';
import { apiFetch, ApiError, type CapabilitiesResponse } from '@/lib/api';
import { PageHeader, ErrorPanel } from '@/components/ui';

export const dynamic = 'force-dynamic';

/**
 * The capability matrix, rendered from the same registry the publisher enforces.
 * This page exists so the operator can see exactly where the platforms stop —
 * rather than discovering a limit when a post fails.
 */
export default async function CapabilitiesPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: CapabilitiesResponse;
  try {
    data = await apiFetch<CapabilitiesResponse>('/platforms/capabilities', { cookie });
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403
        ? 'Sign in to view platform capabilities.'
        : (err as Error).message;
    return (
      <>
        <PageHeader title="Platform Limits" />
        <div className="p-8"><ErrorPanel title="Unavailable" message={message} /></div>
      </>
    );
  }

  const features = Object.keys(data.matrix);
  const platforms = data.supported;

  return (
    <>
      <PageHeader
        title="Platform Limits"
        description="What each platform's official API genuinely permits. The system enforces exactly this — it never offers a control that cannot work."
      />

      <div className="space-y-6 p-8">
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-ink-border">
                  <th className="px-5 py-3 text-left label">Capability</th>
                  {platforms.map((platform) => (
                    <th key={platform} className="px-5 py-3 text-left label">
                      {platform}
                      {!data.configured.includes(platform) && (
                        <span className="ml-2 font-normal normal-case tracking-normal text-bone-dim">
                          (not configured)
                        </span>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {features.map((feature) => (
                  <tr key={feature} className="border-b border-ink-border last:border-0">
                    <td className="px-5 py-3.5 text-bone-muted">{feature}</td>
                    {platforms.map((platform) => {
                      const cell = data.matrix[feature]?.[platform];
                      return (
                        <td key={platform} className="px-5 py-3.5 align-top">
                          <div className={cell?.supported ? 'text-state-ok' : 'text-bone-dim'}>
                            {cell?.supported ? '✓ Supported' : '✕ Not supported'}
                          </div>
                          {cell?.note && (
                            <div className="mt-1 max-w-xs text-xs leading-relaxed text-bone-dim">
                              {cell.note}
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="card card-pad">
            <div className="label">How scheduling actually works</div>
            <div className="mt-3 space-y-3 text-sm leading-relaxed text-bone-muted">
              <p>
                <span className="text-bone">Facebook</span> accepts a future timestamp, so this
                system hands the time to Facebook and Facebook publishes it. Nothing on our side
                needs to be awake.
              </p>
              <p>
                <span className="text-bone">Instagram and TikTok</span> accept no future timestamp.
                Every &ldquo;scheduled&rdquo; post on those platforms — in any product — is that
                product&rsquo;s own scheduler waking up and publishing at the target moment. Ours
                stores the intent in Postgres and re-arms its timers on restart, so losing the
                queue costs punctuality rather than the post.
              </p>
            </div>
          </div>

          <div className="card card-pad">
            <div className="label">Planned platforms</div>
            <p className="mt-3 text-sm leading-relaxed text-bone-muted">
              The adapter layer is built so these can be added without touching the pipeline. They
              are listed as planned rather than shown as broken toggles, because nothing here
              pretends to work before it does.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {data.planned.map((platform) => (
                <span key={platform} className="pill border-ink-border text-bone-dim">{platform}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
