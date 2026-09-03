# Troubleshooting

## Nothing is being generated

Check `GET /api/health` → `integrations`. Then in order:

1. **Autonomous mode off.** It is off by default and cannot be enabled without a
   working LLM provider.
2. **Kill switch engaged.** The Overview page shows this prominently.
3. **Queue is full.** The loop is demand-driven: at or above `maxQueueHours` it
   deliberately stops producing. Check Automation → queue depth.
4. **Budget exceeded.** `GET /api/cost`. The budget gate refuses to dispatch
   before spending, so generation stops cleanly rather than overrunning.
5. **No research provider.** Set `RSS_FEEDS` — it needs no API key.

## "This instance is already initialized"

Registration is single-use by design, so an exposed instance cannot be joined by
a stranger. An existing admin invites further users via `POST /api/auth/users`.

## Instagram publishing fails

| Error | Cause |
| --- | --- |
| `not publicly resolvable` | `S3_PUBLIC_BASE_URL` is localhost or a private address. Meta fetches your media over the internet. |
| `OAuthException` / 401 | Token expired or a permission was revoked. Reconnect the account. |
| `publishing limit reached` | The rolling 100-post/24h cap. The system checks before publishing and defers. |
| `Media container ERROR` | Meta rejected the media. Check dimensions, codec, and duration against Platform Limits. |
| `NOT SUPPORTED BY CURRENT API: ... delete` | Correct. Instagram exposes no delete for API-published media; remove it in the app. |

**Instagram requires a Professional account linked to a Facebook Page.** A
personal account cannot publish through the API, and no configuration changes
that.

## TikTok posts are private

Expected until your API client passes TikTok's audit. Unaudited clients have all
posts forced to `SELF_ONLY`. There is no parameter that overrides it. Once TikTok
approves your client, mark the account audited in the dashboard.

## "Privacy level is not permitted for this creator"

TikTok's `creator_info` returned a narrower set of options than requested — the
creator has restricted who can see their posts. The system honors what the
creator permits rather than overriding it.

## Scheduled posts go out late

The worker was down at the scheduled time. Instagram and TikTok have no
scheduling API, so the worker is the scheduler. The reconciler publishes overdue
jobs on boot and logs `overdue: N`. Alert on the worker process.

Facebook posts are unaffected — those are scheduled natively by Facebook.

## Everything lands in FLAGGED

The exception queue is working. Read `flagReason` on each piece; the common
causes:

- **Fact gate** — too few claims could be verified. Usually means thin sources.
  Add better feeds to `RSS_FEEDS`.
- **Brand QA warning under autonomous mode** — unattended operation is stricter
  than supervised. A `WARN` ships when a human is reviewing and is flagged when
  nobody is.
- **Copyright risk** — an asset has no recorded license. Public availability is
  not a license.
- **Near-duplicate** — too similar to something recently published.

## Analytics show "not reported"

That metric is genuinely unavailable from that platform's API. Instagram
deprecated `impressions`, `plays`, `video_views`, `profile_views`, and
`website_clicks` — requesting them now returns an error. They are stored as
absent rather than zero, because a fabricated zero would be indistinguishable
from real poor performance and would corrupt the learning engine.

## Reel rendering fails

```bash
ffmpeg -encoders | grep -E 'libx264|aac'
```

Both must appear. Some bundled FFmpeg builds (including Playwright's) are
stripped and cannot encode H.264. The compositor checks this up front and throws
`ProviderNotConfiguredError` naming exactly what is missing, rather than
producing a file the platforms would reject.

## Database connection errors under load

Prisma's default pool is small. Add `?connection_limit=20` to `DATABASE_URL`, and
remember the API and worker each hold their own pool.

## Reading what happened

Every stage is recorded:

- `GET /api/logs/agents` — agent runs and errors
- `GET /api/logs/publishing` — publish attempts with the raw platform response
- `GET /api/logs/audit` — every privileged action
- `GET /api/content/:id` — full provenance for one piece: sources, claims, QA
  results, publish attempts, analytics, and what it cost to produce
