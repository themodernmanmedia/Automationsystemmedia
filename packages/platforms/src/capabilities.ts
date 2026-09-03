/**
 * Machine-readable capability registry.
 *
 * This is the runtime source of truth behind docs/platform-capabilities.md. The
 * dashboard renders controls from it, the QA agent validates against it, and the
 * scheduler picks its strategy from it. Keeping it as data rather than scattered
 * `if (platform === 'INSTAGRAM')` branches is what makes adding YouTube later a
 * matter of adding a record plus an adapter.
 *
 * Every value traces to platform documentation as researched 2026-09-03. Values
 * marked VERIFY in a note should be re-confirmed before production.
 */
import type { PlatformCapabilities, PlatformName } from './types.js';

const MB = 1024 * 1024;

export const INSTAGRAM_CAPABILITIES: PlatformCapabilities = {
  platform: 'INSTAGRAM',
  displayName: 'Instagram',

  canPostImage: true,
  canPostVideo: true,
  canPostCarousel: true,
  canPostStory: true,

  // The defining constraint: the Graph API accepts no future publish time.
  canSchedule: false,
  scheduleStrategy: 'SELF_TIMED',

  // No delete endpoint is exposed for API-published media.
  canDelete: false,
  canUpdate: true, // caption edits only, and limited

  canReadAnalytics: true,
  canReadAccountAnalytics: true,
  supportsWebhooks: true,

  carouselMin: 2,
  carouselMax: 10,
  captionMaxLength: 2200,
  hashtagMax: 30,

  image: {
    formats: ['image/jpeg', 'image/png'],
    maxFileSizeBytes: 8 * MB,
    minWidth: 320,
    maxWidth: 1440,
    aspectRatioMin: 0.8, // 4:5
    aspectRatioMax: 1.91, // 1.91:1
    recommendedResolution: '1080x1350',
  },
  video: {
    formats: ['video/mp4', 'video/quicktime'],
    maxFileSizeBytes: 1024 * MB,
    minDurationSec: 5,
    maxDurationSec: 90, // API-published Reels are capped at 90s
    aspectRatioMin: 0.5625, // 9:16
    aspectRatioMax: 0.5625,
    recommendedResolution: '1080x1920',
  },

  postsPer24h: 100, // rolling window; a carousel counts as one
  apiCallsPerHour: 200,

  // Meta fetches media from a URL we supply. We never upload bytes to Meta.
  mediaDelivery: 'PULL_FROM_URL',

  requiredScopes: [
    'instagram_business_basic',
    'instagram_business_content_publish',
    'instagram_business_manage_insights',
  ],

  notes: {
    canSchedule:
      'The Instagram Graph API accepts no scheduled_publish_time. Scheduling is performed by this system: the job is persisted and a worker publishes at the target moment.',
    canDelete:
      'NOT SUPPORTED BY CURRENT API: the Graph API exposes no delete for API-published media. Remove the post manually in the Instagram app.',
    mediaDelivery:
      'Meta fetches media from image_url/video_url. Media must be at a publicly resolvable URL — S3-compatible storage is a hard requirement.',
    analytics:
      'impressions, plays, video_views (non-Reels), profile_views, website_clicks and phone_call_clicks are deprecated and return errors. Use views.',
    accountType: 'Requires an Instagram Professional (Business or Creator) account linked to a Facebook Page.',
    postsPer24h: 'Enforced on media_publish. Check GET /{ig-user-id}/content_publishing_limit before publishing.',
  },
};

export const TIKTOK_CAPABILITIES: PlatformCapabilities = {
  platform: 'TIKTOK',
  displayName: 'TikTok',

  canPostImage: true, // photo posts, which are multi-image by nature
  canPostVideo: true,
  canPostCarousel: true, // photo post with multiple images
  canPostStory: false,

  canSchedule: false,
  scheduleStrategy: 'SELF_TIMED',

  canDelete: false,
  canUpdate: false,

  canReadAnalytics: true, // Display API, own videos only
  canReadAccountAnalytics: true, // user.info.stats
  supportsWebhooks: false,

  carouselMin: 1,
  carouselMax: 35,
  captionMaxLength: 2200,
  hashtagMax: 30,

  image: {
    formats: ['image/jpeg', 'image/webp'],
    maxFileSizeBytes: 20 * MB,
    recommendedResolution: '1080x1920',
  },
  video: {
    formats: ['video/mp4', 'video/quicktime', 'video/webm'],
    maxFileSizeBytes: 4096 * MB,
    minDurationSec: 3,
    // Real ceiling is per-creator: max_video_post_duration_sec from creator_info.
    maxDurationSec: 600,
    aspectRatioMin: 0.5625,
    aspectRatioMax: 1.0,
    recommendedResolution: '1080x1920',
  },

  mediaDelivery: 'BOTH', // FILE_UPLOAD, or PULL_FROM_URL with a verified domain

  requiredScopes: ['user.info.basic', 'user.info.stats', 'video.publish', 'video.upload', 'video.list'],

  notes: {
    audit:
      'Until the API client passes TikTok audit, ALL posts are forced to SELF_ONLY (private) visibility regardless of the requested privacy level. Audit takes roughly 2-4 weeks.',
    creatorInfo:
      'creator_info/query must be called before every post. It returns the permitted privacy levels, comment/duet/stitch permissions, and the creator max video duration, all of which must be honored.',
    canSchedule: 'No scheduling API. This system holds the job and publishes at the target time.',
    canDelete: 'NOT SUPPORTED BY CURRENT API: the Content Posting API has no delete endpoint.',
    canUpdate: 'NOT SUPPORTED BY CURRENT API: published posts cannot be edited via API.',
    trends:
      'NOT AVAILABLE: the TikTok Research API is restricted to approved academic and nonprofit researchers. There is no commercial trend feed.',
    maxDurationSec: 'The real limit is per-creator; read max_video_post_duration_sec from creator_info.',
  },
};

export const FACEBOOK_CAPABILITIES: PlatformCapabilities = {
  platform: 'FACEBOOK',
  displayName: 'Facebook Page',

  canPostImage: true,
  canPostVideo: true,
  canPostCarousel: true,
  canPostStory: false,

  // The one platform of the three with genuine native scheduling.
  canSchedule: true,
  scheduleStrategy: 'DELEGATED',

  canDelete: true,
  canUpdate: true,

  canReadAnalytics: true,
  canReadAccountAnalytics: true,
  supportsWebhooks: true,

  carouselMin: 2,
  carouselMax: 10,
  captionMaxLength: 63206,
  hashtagMax: 30,

  image: {
    formats: ['image/jpeg', 'image/png', 'image/gif'],
    maxFileSizeBytes: 10 * MB,
    recommendedResolution: '1200x630',
  },
  video: {
    formats: ['video/mp4', 'video/quicktime'],
    maxFileSizeBytes: 10240 * MB,
    minDurationSec: 1,
    maxDurationSec: 14400,
    recommendedResolution: '1080x1920',
  },

  mediaDelivery: 'BOTH',

  requiredScopes: [
    'pages_show_list',
    'pages_read_engagement',
    'pages_manage_posts',
    'pages_read_user_content',
    'read_insights',
  ],

  notes: {
    canSchedule:
      'Native scheduling via published=false + scheduled_publish_time (Unix seconds, 10 minutes to 30 days out). This system delegates timing to Facebook rather than holding the job locally.',
    tokens:
      'Page access tokens do not expire while the underlying long-lived user token is valid and the user retains their Page role. Tokens are resolved at publish time so a lost role surfaces as an explicit reconnect prompt.',
  },
};

const REGISTRY: Partial<Record<PlatformName, PlatformCapabilities>> = {
  INSTAGRAM: INSTAGRAM_CAPABILITIES,
  TIKTOK: TIKTOK_CAPABILITIES,
  FACEBOOK: FACEBOOK_CAPABILITIES,
};

/** Platforms with a working adapter today. */
export const SUPPORTED_PLATFORMS: PlatformName[] = ['INSTAGRAM', 'TIKTOK', 'FACEBOOK'];

/**
 * Platforms the architecture anticipates but that have no adapter yet. Listed
 * explicitly so the UI can show them as "planned" rather than pretending they
 * work — the brief's no-fake-integrations rule.
 */
export const PLANNED_PLATFORMS: PlatformName[] = ['YOUTUBE', 'X', 'LINKEDIN', 'PINTEREST', 'THREADS'];

export function getCapabilities(platform: PlatformName): PlatformCapabilities | undefined {
  return REGISTRY[platform];
}

export function allCapabilities(): PlatformCapabilities[] {
  return SUPPORTED_PLATFORMS.map((p) => REGISTRY[p]).filter((c): c is PlatformCapabilities => Boolean(c));
}

/**
 * Renders the capability matrix for the dashboard, including the human-readable
 * reason a capability is missing. The UI shows `NOT SUPPORTED BY CURRENT API`
 * plus this note instead of a button that would throw.
 */
export interface CapabilityCell {
  supported: boolean;
  note?: string;
}

export function capabilityMatrix(): Record<string, Record<PlatformName, CapabilityCell>> {
  const features: Array<[string, keyof PlatformCapabilities]> = [
    ['Image posting', 'canPostImage'],
    ['Carousel posting', 'canPostCarousel'],
    ['Video / Reel posting', 'canPostVideo'],
    ['Story posting', 'canPostStory'],
    ['Native scheduling', 'canSchedule'],
    ['Post analytics', 'canReadAnalytics'],
    ['Account analytics', 'canReadAccountAnalytics'],
    ['Delete post', 'canDelete'],
    ['Edit post', 'canUpdate'],
    ['Webhooks', 'supportsWebhooks'],
  ];

  const matrix: Record<string, Record<PlatformName, CapabilityCell>> = {};
  for (const [label, key] of features) {
    const row = {} as Record<PlatformName, CapabilityCell>;
    for (const platform of SUPPORTED_PLATFORMS) {
      const caps = REGISTRY[platform];
      if (!caps) continue;
      const supported = Boolean(caps[key]);
      const note = caps.notes[key as string];
      row[platform] = note ? { supported, note } : { supported };
    }
    matrix[label] = row;
  }
  return matrix;
}
