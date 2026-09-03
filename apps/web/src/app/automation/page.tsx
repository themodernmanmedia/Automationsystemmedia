import { headers } from 'next/headers';
import { apiFetch, ApiError, type AutomationResponse } from '@/lib/api';
import { PageHeader, ErrorPanel } from '@/components/ui';
import { AutomationControls } from './controls';

export const dynamic = 'force-dynamic';

export default async function AutomationPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: AutomationResponse;
  try {
    data = await apiFetch<AutomationResponse>('/automation', { cookie });
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403
        ? 'Sign in to view the automation control center.'
        : (err as Error).message;
    return (
      <>
        <PageHeader title="Automation" />
        <div className="p-8">
          <ErrorPanel title="Unavailable" message={message} />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Automation Control Center"
        description="Start, pause, and stop the system. Every control here takes effect immediately."
      />
      <div className="p-8">
        <AutomationControls initial={data} />
      </div>
    </>
  );
}
