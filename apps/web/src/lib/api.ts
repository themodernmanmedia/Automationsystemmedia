/**
 * Typed API client.
 *
 * Server components call the API directly; the browser goes through the Next
 * rewrite. Either way the session cookie is the only credential, and no
 * platform token ever reaches this code.
 */
const API_BASE = process.env.API_BASE_URL ?? 'http://localhost:4000';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { cookie?: string } = {},
): Promise<T> {
  const { cookie, ...rest } = init;
  const res = await fetch(`${API_BASE}/api${path}`, {
    ...rest,
    headers: {
      'content-type': 'application/json',
      ...(cookie ? { cookie } : {}),
      ...rest.headers,
    },
    cache: 'no-store',
  });

  const text = await res.text();
  const body = text ? (JSON.parse(text) as unknown) : {};

  if (!res.ok) {
    const err = body as { message?: string; code?: string };
    throw new ApiError(err.message ?? `Request failed (${res.status})`, res.status, err.code);
  }
  return body as T;
}

/** Browser-side call through the Next rewrite, so cookies travel automatically. */
export async function clientFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...init.headers },
    credentials: 'include',
  });
  const text = await res.text();
  const body = text ? (JSON.parse(text) as unknown) : {};
  if (!res.ok) {
    const err = body as { message?: string; code?: string };
    throw new ApiError(err.message ?? `Request failed (${res.status})`, res.status, err.code);
  }
  return body as T;
}

/* ------------------------------- API types ------------------------------- */

export interface Overview {
  today: { published: number; queued: number; failed: number; flagged: number };
  accounts: Array<{ platform: string; username: string; followerCount: number | null }>;
  followers: number;
  weekAnalytics: Record<string, number | null>;
  trendingTopics: Array<{
    id: string;
    title: string;
    category: string;
    compositeScore: number | null;
    isBreakingNews: boolean;
  }>;
  automation: { autonomousMode: boolean; killSwitch: boolean; publishingPaused: boolean };
  integrations: Record<string, boolean>;
}

export interface AutomationResponse {
  state: {
    autonomousMode: boolean;
    killSwitch: boolean;
    publishingPaused: boolean;
    agentFlags: Record<string, boolean>;
    minQueueHours: number;
    targetQueueHours: number;
    maxQueueHours: number;
    maxPostsPerDay: number;
  };
  queue: {
    scheduledCount: number;
    hoursOfContent: number;
    status: 'CRITICAL' | 'LOW' | 'HEALTHY' | 'FULL';
    shouldGenerate: boolean;
    postsNeeded: number;
  };
  agents: Array<{
    key: string;
    enabled: boolean;
    status: 'RUNNING' | 'IDLE' | 'PAUSED' | 'ERROR';
    lastRunAt: string | null;
    runsLast24h: number;
    failuresLast24h: number;
  }>;
  integrations: Record<string, boolean>;
  integrationErrors: Record<string, string>;
}

export interface AccountsResponse {
  accounts: Array<{
    id: string;
    platform: string;
    username: string;
    displayName: string | null;
    profileImageUrl: string | null;
    accountType: string | null;
    status: string;
    statusMessage: string | null;
    followerCount: number | null;
    scopes: string[];
    lastSyncAt: string | null;
    lastPublishAt: string | null;
    lastPublishError: string | null;
    postCount: number;
    tokenStatus: 'VALID' | 'EXPIRING' | 'EXPIRED' | 'MISSING';
    tokenExpiresAt: string | null;
    isAudited: boolean;
    auditWarning: string | null;
    capabilities: {
      canSchedule: boolean;
      scheduleStrategy: string;
      canDelete: boolean;
      canPostCarousel: boolean;
      canPostVideo: boolean;
      notes: Record<string, string>;
    } | null;
  }>;
}

export interface CapabilitiesResponse {
  matrix: Record<string, Record<string, { supported: boolean; note?: string }>>;
  supported: string[];
  planned: string[];
  configured: string[];
}

export interface CostResponse {
  dailySpent: number;
  dailyLimit: number;
  monthlySpent: number;
  monthlyLimit: number;
  halted: boolean;
  breakdown: Array<{ service: string; costUsd: number; calls: number }>;
}
