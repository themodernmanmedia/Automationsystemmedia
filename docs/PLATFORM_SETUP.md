# Platform Setup

Exactly which credentials you need and how to obtain them. Budget real time for
this: **Meta App Review and TikTok audit are the long poles**, and no amount of
code shortens them.

## 0. Before anything else

| Requirement | Why |
| --- | --- |
| A domain with HTTPS | OAuth redirect URIs must be HTTPS in production |
| S3-compatible storage with public read | **Instagram cannot publish without it** — Meta fetches media from a URL |
| An LLM API key | Nothing generates without one |
| Postgres 16+ and Redis 7+ | Durable state and job timers |
| FFmpeg with libx264 + AAC | Reel rendering. `ffmpeg -encoders \| grep libx264` must return a match |

## 1. Core secrets

```bash
openssl rand -base64 32   # ENCRYPTION_KEY
openssl rand -base64 32   # SESSION_SECRET
```

`ENCRYPTION_KEY` encrypts every platform token at rest. **If you lose it, every
connected account must be reconnected** — the ciphertext is unrecoverable. Store
it in a secret manager, not in the repository.

## 2. Meta — Instagram and Facebook (one app covers both)

Instagram publishing has strict prerequisites. Confirm all four before starting:

1. An Instagram **Professional** account (Business or Creator) — a personal
   account cannot use the API, and there is no workaround.
2. A **Facebook Page** linked to that Instagram account.
3. A **Meta Business account** owning both.
4. A Meta developer app of type **Business**.

Then:

1. <https://developers.facebook.com/apps> → Create App → Business.
2. Add the **Instagram** and **Facebook Login for Business** products.
3. Under Facebook Login → Settings, add your exact redirect URI:
   `https://your-domain.com/api/oauth/meta/callback` (no wildcards).
4. Request these permissions in App Review:
   - `instagram_business_basic`
   - `instagram_business_content_publish`
   - `instagram_business_manage_insights`
   - `pages_show_list`, `pages_manage_posts`, `pages_read_engagement`, `read_insights`
5. Copy the App ID and App Secret into `META_APP_ID` / `META_APP_SECRET`.

> The older `instagram_basic` and `instagram_content_publish` scopes were
> **deprecated on 2025-01-27**. Do not request them.

**App Review** requires a screencast of your integration and a written
explanation. Expect days to weeks. Until it passes, only users with a role on
the app can authorize it — which is enough to test with your own account.

## 3. TikTok

1. <https://developers.tiktok.com> → register → create an app.
2. Add the **Content Posting API** and **Login Kit** products.
3. Set the redirect URI: `https://your-domain.com/api/oauth/tiktok/callback`.
4. Request scopes: `user.info.basic`, `user.info.stats`, `video.publish`,
   `video.upload`, `video.list`.
5. Copy the client key and secret into `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET`.

> **Read this before expecting public posts.** Until your client passes TikTok's
> audit, **every post it creates is forced to `SELF_ONLY` (private)** regardless
> of the privacy level you request. The audit takes roughly 2–4 weeks with
> several rounds of feedback. The dashboard marks the account `AUDIT PENDING`
> so this is never a surprise. Once approved, set `isAudited` on the account
> (Social Accounts → account → mark audited).

**Domain verification** is also required if you want TikTok to pull media from
your URLs rather than receiving uploaded bytes.

## 4. Object storage

Any S3-compatible provider. Cloudflare R2 is the cheapest sane default because
egress is free and Meta will be fetching every image you publish.

```bash
S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com
S3_REGION=auto
S3_BUCKET=modernman-media
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_PUBLIC_BASE_URL=https://media.your-domain.com
```

`S3_PUBLIC_BASE_URL` **must be publicly resolvable from the internet.** Meta's
servers fetch from it. A localhost or private-network URL will fail every time,
and the system's validation rejects it before publishing rather than letting the
API call fail.

## 5. AI providers

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

Or `LLM_PROVIDER=openai` with `OPENAI_API_KEY`. Both are fully implemented and
interchangeable.

Optional: `IMAGE_PROVIDER`, `VOICE_PROVIDER` (`ELEVENLABS_API_KEY` +
`ELEVENLABS_VOICE_ID`, or OpenAI TTS). An unset provider throws
`ProviderNotConfiguredError` when called — it never returns fake media.

## 6. Research sources

**RSS needs no API key and works immediately**, which is why it is the default:

```bash
RSS_FEEDS=https://feeds.bbci.co.uk/news/business/rss.xml,https://techcrunch.com/feed/
```

Optionally add `SEARCH_PROVIDER=brave` with `BRAVE_SEARCH_API_KEY`, or Tavily.

> There is **no legitimate commercial trend API** from Instagram, TikTok, or
> Facebook. TikTok's Research API is restricted to approved academics and
> nonprofits. See `docs/API_LIMITATIONS.md` §5.

## 7. First run

```bash
pnpm install
pnpm db:migrate
pnpm dev:api      # :4000
pnpm dev:web      # :3000
pnpm dev:worker
```

1. Open <http://localhost:3000/login> and create the owner account.
   Registration then closes — further users are invited by an admin.
2. Run `pnpm db:seed` to create the default brand.
3. Connect your accounts under **Social Accounts**.
4. Leave autonomous mode **off** until you have seen what the system produces.
   Generate a few pieces, read them, then enable it.

## Estimated monthly cost

At roughly 5 posts/day, all-in:

| Item | Estimate |
| --- | --- |
| LLM (research, writing, QA) | $40–120 |
| Image generation (optional) | $0–90 |
| Voice for Reels (optional) | $0–40 |
| Search API (optional; RSS is free) | $0–30 |
| Object storage + egress | $2–10 |
| Postgres + Redis + hosting | $20–60 |
| **Total** | **$60–350** |

The wide range is generation choices: text-only carousels are cheap, while
AI-generated imagery and voiced Reels are most of the cost. Set
`DAILY_COST_LIMIT_USD` and `MONTHLY_COST_LIMIT_USD` — the budget gate refuses
to dispatch a call once the ceiling is reached, before the money is spent.
