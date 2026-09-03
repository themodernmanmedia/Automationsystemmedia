# Platform Capability Matrix

> **Status:** compiled 2026-09-03 from official-API research. The sandbox this was built
> in blocks direct egress to `developers.facebook.com` and `developers.tiktok.com`, so the
> matrix below was assembled from search-indexed documentation and vendor engineering
> writeups rather than by fetching the primary docs byte-for-byte. **Every row marked
> ⚠️ must be re-verified against the primary doc before you go to production.** The
> machine-readable source of truth that the running system actually enforces lives in
> `packages/platforms/src/capabilities.ts` — this document and that file must be kept in
> sync, and a test asserts the capability registry is internally consistent.

## Legend

| Symbol | Meaning |
| --- | --- |
| ✅ | Supported via official API, implemented in this system |
| ⚠️ | Supported by the API but with material restrictions (see notes) |
| 🔶 | Supported by the API, **not yet implemented** here |
| ❌ | **Not supported by the official API.** The UI shows `NOT SUPPORTED BY CURRENT API` |

## Master matrix

| Capability | Instagram | TikTok | Facebook Page |
| --- | --- | --- | --- |
| OAuth connect | ✅ | ✅ | ✅ |
| Token refresh | ✅ 60d long-lived, refreshable | ✅ 24h access / 365d refresh | ✅ Page tokens (long-lived) |
| Read account profile | ✅ | ✅ | ✅ |
| Single image post | ✅ | ❌ (photo post = carousel-style only) | ✅ |
| Carousel post | ✅ 2–10 items | ⚠️ photo post, 1–35 images | ✅ (multi-photo) |
| Video / Reel post | ✅ REELS | ✅ | ✅ |
| Story post | ⚠️ STORIES container | ❌ | 🔶 |
| **Native scheduling** | ❌ **no `scheduled_publish_time`** | ❌ | ✅ `published=false` + `scheduled_publish_time` |
| Post analytics | ✅ Insights | ⚠️ Display API, own videos | ✅ Insights |
| Account analytics | ✅ | ⚠️ `user.info.stats` | ✅ |
| Delete post | ❌ not exposed for API-published media | ❌ | ✅ |
| Edit published post | ⚠️ caption only, limited | ❌ | ✅ |
| Comment read / reply | 🔶 | 🔶 | 🔶 |
| DM automation | ❌ out of scope by policy choice | ❌ | ❌ |
| Webhooks | 🔶 available | ❌ | 🔶 available |
| Trend / discovery data | ❌ | ❌ Research API is academics-only | ❌ |

---

## Instagram — Content Publishing API

**Account requirements.** Instagram **Professional** account (Business or Creator),
linked to a Facebook Page, owned by a Meta Business account, addressed through a Meta
developer app with App Review approval.

**Permissions.** `instagram_business_basic`, `instagram_business_content_publish`,
`instagram_business_manage_insights`. ⚠️ The older `instagram_basic` /
`instagram_content_publish` scopes were **deprecated 2025-01-27** — do not use them.

**Publishing is a two-step container flow.** There is no single-call publish:

```
POST /{ig-user-id}/media          → returns a creation_id (container)
   ↳ (video/reel: poll GET /{creation_id}?fields=status_code until FINISHED)
POST /{ig-user-id}/media_publish  → body: creation_id → returns the live media id
```

Carousels are three steps: create one child container per item with
`is_carousel_item=true`, then a parent container with `media_type=CAROUSEL` and
`children=[...]`, then publish the parent.

**Media must be fetched by Meta from a public URL.** You do not upload bytes to Meta.
You pass `image_url` / `video_url` and Meta's servers pull it. This is why the system
requires object storage that can mint publicly-readable (or presigned, publicly
resolvable) URLs — see `docs/ARCHITECTURE.md` § Storage.

**Rate limits.**
- **100 API-published posts per rolling 24 hours** per IG account. A carousel counts as
  **one** post. Check current consumption with
  `GET /{ig-user-id}/content_publishing_limit`. The system queries this **before every
  publish** and refuses rather than burning a slot on a call that will fail.
- Business Use Case limit: ~200 API calls per user per hour.

**Media requirements** (⚠️ verify — Meta tightens these):

| | Requirement |
| --- | --- |
| Image | JPEG preferred; 320–1440 px wide; aspect 4:5 → 1.91:1; ≤ 8 MB |
| Reel | MP4/MOV, H.264 (or HEVC), AAC audio; 9:16, 1080×1920 recommended; **5–90 s via API**; ≤ 1 GB |
| Carousel | 2–10 items |
| Caption | 2,200 characters ⚠️ |
| Hashtags | 30 per post ⚠️ |

**No native scheduling.** This is the single most architecture-defining fact in this
document. Instagram's API accepts no future timestamp. Any "scheduled Instagram post"
in any product on earth is that product's own scheduler waking up at the target time
and firing `media_publish` itself. The Modern Man OS therefore owns a durable scheduler
(BullMQ delayed jobs backed by Postgres rows, so a Redis loss cannot silently drop a
scheduled post) — see `apps/worker`.

**Analytics.** ⚠️ Significant 2025–2026 deprecations. `impressions` (media + user),
`plays`, `video_views` (non-Reels), `profile_views`, `website_clicks`,
`phone_call_clicks` are **gone** — requesting them returns an *error*, not a zero. The
replacement everywhere is **`views`**. The system's metric allowlist lives in
`packages/platforms/src/instagram/metrics.ts` and deliberately never requests a
deprecated metric.

---

## TikTok — Content Posting API

**Permissions.** `video.publish` (Direct Post — goes live), `video.upload` (lands in the
creator's inbox as a draft they finish manually), `user.info.basic`/`user.info.stats`,
`video.list`.

**The audit gate — read this before promising yourself automation.**
Until your API client passes TikTok's audit, **every post your app creates is forced to
`SELF_ONLY` (private) visibility**, regardless of what you request. The audit takes
roughly 2–4 weeks and usually involves several rounds of feedback. Until it passes,
TikTok automation in this system is real but privately-visible — the dashboard says so
explicitly on the account card rather than pretending the post is public.

**You must query creator info first.** `POST /v2/post/publish/creator_info/query/`
returns the creator's permitted privacy levels, whether comment/duet/stitch are allowed,
and `max_video_post_duration_sec`. Posting without honoring these is both a policy
violation and a guaranteed rejection. The system calls this before every TikTok publish
and validates the request against the response.

**Flow.**
```
POST /v2/post/publish/creator_info/query/     → permitted options
POST /v2/post/publish/video/init/             → publish_id + upload_url
PUT  {upload_url}                             → the actual bytes (chunked)
GET  /v2/post/publish/status/fetch/           → poll until PUBLISH_COMPLETE
```
Unlike Meta, TikTok **does** accept the bytes directly (`FILE_UPLOAD`), or will pull from
a URL (`PULL_FROM_URL`) if the domain is verified against your app.

**No native scheduling.** Same as Instagram — the system schedules.

**No commercial trend data.** The TikTok **Research API is restricted to approved
academic and nonprofit researchers**; commercial applications are routinely rejected.
There is therefore **no legitimate TikTok trend feed** available to this product. The
trend engine uses news/RSS/search sources instead and does not pretend otherwise.

---

## Facebook — Pages API

**Permissions.** `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
`pages_read_user_content`, `read_insights`, plus `business_management` in most setups.

**Facebook is the one platform with real native scheduling.** Pass `published=false`
with `scheduled_publish_time` (Unix seconds, between 10 minutes and 30 days out) and
Facebook holds and publishes it for you. The system detects this capability from the
registry and **hands scheduling to Facebook** rather than holding the job locally —
a concrete payoff of the capability-matrix design rather than a decorative abstraction.

**Tokens.** User token → long-lived user token → **Page access token**, which does not
expire as long as the underlying long-lived user token stays valid and the user keeps
their Page role. Page tokens are resolved at publish time so a revoked role surfaces as
an explicit reconnect prompt rather than an opaque 400.

---

## What this system deliberately does not do

| | Why |
| --- | --- |
| Scrape any platform's web UI | ToS violation, account-ban risk. Official APIs only. |
| Automate DMs | High policy risk, low content value. |
| Post to a personal (non-Professional) IG account | The API cannot; no workaround exists that is not a ToS violation. |
| Use TikTok trend data commercially | Research API is academics-only. |
| Auto-publish unverified factual claims | See `docs/ARCHITECTURE.md` § Fact gate. |
| Auto-publish HIGH copyright-risk assets | Routed to the exception queue for a human. |
