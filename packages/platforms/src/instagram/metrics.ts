/**
 * Instagram metric allowlist.
 *
 * Meta deprecated a large part of the Insights surface across 2025-2026.
 * Requesting a deprecated metric does not return zero — it errors the whole
 * request. So the allowlist is explicit, and the deprecated list is kept
 * alongside it so the UI can say "this platform no longer reports it" instead
 * of showing a misleading 0.
 */

export const IG_MEDIA_METRICS = [
  'reach',
  'likes',
  'comments',
  'shares',
  'saved',
  'views',
  'total_interactions',
] as const;

export const IG_ACCOUNT_METRICS = ['reach', 'views'] as const;

/** Deprecated by Meta. Never request these; report them as unavailable. */
export const IG_DEPRECATED_METRICS = [
  'impressions',
  'plays',
  'video_views',
  'profile_views',
  'website_clicks',
  'phone_call_clicks',
  'text_message_clicks',
  'email_contacts',
] as const;
