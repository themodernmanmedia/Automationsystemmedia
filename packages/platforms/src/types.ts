/**
 * The unified platform abstraction.
 *
 * The governing rule: capabilities differ per platform and the system must know
 * this at runtime, not assume uniformity. Instagram cannot schedule or delete;
 * Facebook can do both. So every adapter declares what it can do, callers check
 * before acting, and anything unsupported throws CapabilityNotSupportedError
 * rather than silently doing nothing.
 */

export type PlatformName = 'INSTAGRAM' | 'TIKTOK' | 'FACEBOOK' | 'YOUTUBE' | 'X' | 'LINKEDIN' | 'PINTEREST' | 'THREADS';

export type MediaKind = 'IMAGE' | 'VIDEO' | 'CAROUSEL' | 'STORY' | 'REEL';

/**
 * How a scheduled post actually gets published at the right time.
 * - DELEGATED: the platform accepts a future timestamp and publishes for us (Facebook).
 * - SELF_TIMED: no such API exists; our scheduler wakes up and publishes (Instagram, TikTok).
 * - NONE: immediate publishing only.
 */
export type ScheduleStrategy = 'DELEGATED' | 'SELF_TIMED' | 'NONE';

export interface MediaConstraints {
  readonly formats: readonly string[];
  readonly maxFileSizeBytes: number;
  readonly minWidth?: number;
  readonly maxWidth?: number;
  readonly minDurationSec?: number;
  readonly maxDurationSec?: number;
  readonly aspectRatioMin?: number;
  readonly aspectRatioMax?: number;
  readonly recommendedResolution?: string;
}

export interface PlatformCapabilities {
  readonly platform: PlatformName;
  readonly displayName: string;

  readonly canPostImage: boolean;
  readonly canPostVideo: boolean;
  readonly canPostCarousel: boolean;
  readonly canPostStory: boolean;
  readonly canSchedule: boolean;
  readonly scheduleStrategy: ScheduleStrategy;
  readonly canDelete: boolean;
  readonly canUpdate: boolean;
  readonly canReadAnalytics: boolean;
  readonly canReadAccountAnalytics: boolean;
  readonly supportsWebhooks: boolean;

  readonly carouselMin?: number;
  readonly carouselMax?: number;
  readonly captionMaxLength: number;
  readonly hashtagMax: number;

  readonly image: MediaConstraints;
  readonly video: MediaConstraints;

  /** Documented publishing ceiling; the publisher stays under it by construction. */
  readonly postsPer24h?: number;
  readonly apiCallsPerHour?: number;

  /**
   * Media delivery model. Meta FETCHES from a public URL (so storage must be
   * publicly resolvable); TikTok accepts uploaded bytes.
   */
  readonly mediaDelivery: 'PULL_FROM_URL' | 'DIRECT_UPLOAD' | 'BOTH';

  readonly requiredScopes: readonly string[];
  /** Human-readable reasons a capability is absent, shown verbatim in the UI. */
  readonly notes: Readonly<Record<string, string>>;
}

/* ---------------------------- operation types ---------------------------- */

export interface PlatformAccount {
  platformAccountId: string;
  username: string;
  displayName?: string;
  profileImageUrl?: string;
  accountType?: string;
  followerCount?: number;
  raw?: unknown;
}

export interface OAuthTokens {
  accessToken: string;
  refreshToken?: string | null;
  expiresAt?: Date | null;
  refreshExpiresAt?: Date | null;
  scopes: string[];
  raw?: unknown;
}

export interface MediaItem {
  /** Publicly fetchable URL. Required for Meta, which pulls rather than accepts. */
  url: string;
  kind: 'IMAGE' | 'VIDEO';
  mimeType: string;
  width?: number;
  height?: number;
  durationSec?: number;
  fileSizeBytes?: number;
  /** Local path — required by TikTok, which uploads bytes. */
  localPath?: string;
}

export interface CreatePostInput {
  kind: MediaKind;
  media: MediaItem[];
  caption: string;
  /** Absent = publish now. Present = schedule (strategy decided by capabilities). */
  scheduledAt?: Date;
  /** TikTok privacy level; validated against creator_info before use. */
  privacyLevel?: string;
  disableComment?: boolean;
  disableDuet?: boolean;
  disableStitch?: boolean;
  thumbnailUrl?: string;
  idempotencyKey?: string;
}

export interface PublishResult {
  platformPostId: string;
  platformUrl?: string;
  publishedAt: Date;
  /** True when the platform accepted a future timestamp (Facebook). */
  scheduledByPlatform?: boolean;
  /**
   * True when the post is live but not publicly visible — TikTok forces
   * SELF_ONLY for unaudited clients. Surfaced so this is never a surprise.
   */
  restrictedVisibility?: boolean;
  visibilityNote?: string;
  raw?: unknown;
}

export type PostState = 'PENDING' | 'PROCESSING' | 'PUBLISHED' | 'FAILED' | 'SCHEDULED';

export interface PostStatus {
  state: PostState;
  platformPostId?: string;
  error?: string;
  raw?: unknown;
}

/**
 * Normalized analytics. Every metric is nullable and `unavailableMetrics` names
 * what this platform will not return — Instagram has deprecated `impressions`
 * and `plays`, and recording 0 for them would corrupt the learning engine.
 */
export interface NormalizedAnalytics {
  platformPostId: string;
  collectedAt: Date;
  views: number | null;
  reach: number | null;
  impressions: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  watchTimeSec: number | null;
  avgWatchTimeSec: number | null;
  retentionRate: number | null;
  profileVisits: number | null;
  followsGained: number | null;
  clicks: number | null;
  engagementRate: number | null;
  unavailableMetrics: string[];
  raw?: unknown;
}

export interface AccountAnalytics {
  collectedAt: Date;
  followerCount: number | null;
  reach: number | null;
  views: number | null;
  unavailableMetrics: string[];
  raw?: unknown;
}

export interface RateLimitStatus {
  /** Posts already published in the current window, when the platform reports it. */
  used?: number;
  limit?: number;
  remaining?: number;
  resetsAt?: Date;
  /** False when publishing now would exceed a documented limit. */
  canPublish: boolean;
  reason?: string;
}

export interface AdapterContext {
  accessToken: string;
  platformAccountId: string;
  /** TikTok: false until the app passes audit, which forces SELF_ONLY posts. */
  isAudited?: boolean;
}

/**
 * Every platform integration implements this. Methods a platform genuinely
 * cannot perform must throw CapabilityNotSupportedError — never return a
 * fabricated success.
 */
export interface PlatformAdapter {
  readonly platform: PlatformName;
  getPublishingCapabilities(): PlatformCapabilities;

  /** Authorization URL for the OAuth redirect. */
  getAuthorizationUrl(state: string, scopes?: string[]): string;
  exchangeCodeForTokens(code: string): Promise<OAuthTokens>;
  refreshToken(refreshToken: string): Promise<OAuthTokens>;

  getAccount(ctx: AdapterContext): Promise<PlatformAccount>;
  checkRateLimit(ctx: AdapterContext): Promise<RateLimitStatus>;

  createPost(ctx: AdapterContext, input: CreatePostInput): Promise<PublishResult>;
  getPostStatus(ctx: AdapterContext, ref: string): Promise<PostStatus>;

  getAnalytics(ctx: AdapterContext, platformPostId: string): Promise<NormalizedAnalytics>;
  getAccountAnalytics(ctx: AdapterContext): Promise<AccountAnalytics>;

  deletePost(ctx: AdapterContext, platformPostId: string): Promise<void>;
  updatePost(ctx: AdapterContext, platformPostId: string, caption: string): Promise<void>;

  /** Structural validation against this platform's documented constraints. */
  validate(input: CreatePostInput): ValidationIssue[];
}

export interface ValidationIssue {
  severity: 'ERROR' | 'WARNING';
  field: string;
  message: string;
}
