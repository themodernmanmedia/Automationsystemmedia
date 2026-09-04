import { headers } from 'next/headers';
import { apiFetch, ApiError, type BrandResponse } from '@/lib/api';
import { PageHeader, ErrorPanel, EmptyState } from '@/components/ui';
import { BrandEditor } from './editor';

export const dynamic = 'force-dynamic';

export default async function BrandPage() {
  const cookie = (await headers()).get('cookie') ?? '';

  let data: BrandResponse;
  try {
    data = await apiFetch<BrandResponse>('/brand', { cookie });
  } catch (err) {
    const message =
      err instanceof ApiError && err.status === 403
        ? 'Sign in to view brand settings.'
        : (err as Error).message;
    return (
      <>
        <PageHeader title="Brand" />
        <div className="p-8"><ErrorPanel title="Unavailable" message={message} /></div>
      </>
    );
  }

  if (!data.brand) {
    return (
      <>
        <PageHeader title="Brand" />
        <div className="p-8">
          <EmptyState
            title="No brand configured"
            description="Run pnpm db:seed to create the default brand. Everything on this page then drives what the agents produce."
          />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Brand"
        description="These settings drive what the agents produce. Changes apply to content generated from now on."
      />
      <div className="p-8">
        <BrandEditor brand={data.brand} defaults={data.defaults} />
      </div>
    </>
  );
}
