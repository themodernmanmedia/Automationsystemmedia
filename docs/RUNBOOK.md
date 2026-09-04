# Runbook — from empty `.env` to first live post

`PLATFORM_SETUP.md` tells you how to obtain each credential. This tells you the
**order**, which matters more than it looks: two of the steps are approval waits
measured in weeks, and everything else can be done while they run. Start them on
day one and the total elapsed time is the length of the longest wait. Leave them
until you feel "ready" and you add those weeks to the end.

Each phase below states what it needs, what to run, and a **checkpoint** that
proves it worked. Do not move on from a phase whose checkpoint fails — every
later symptom gets harder to read.

---

## The two clocks, and why they go first

| Wait | Typical | Blocks | Does **not** block |
| --- | --- | --- | --- |
| Meta App Review | days–weeks | Publishing to Instagram/Facebook accounts other than your own | Building, generating, connecting **your own** account |
| TikTok audit | ~2–4 weeks, several rounds | Posts being **visible to anyone but you** | Building, generating, connecting, posting — all of it works |

Neither blocks the work in Phases 1–3. Both block being genuinely live. So:

**Phase 0 is not optional and not last.**

---

## Phase 0 — Start the clocks

*~30–60 minutes. Do this before writing any configuration.*

1. Confirm the Instagram prerequisites, because they cannot be worked around and
   people discover them late:
   - Instagram account is **Professional** (Business or Creator). A personal
     account cannot use the API at all.
   - A **Facebook Page** is linked to it.
   - A **Meta Business account** owns both.
2. Create the Meta app (Business type), add Instagram + Facebook Login for
   Business, and **submit for App Review** with the scopes listed in
   `PLATFORM_SETUP.md §2`. Submitting starts the clock; you do not need the rest
   of this system finished to submit.
3. Create the TikTok app, add Content Posting API + Login Kit, and **submit for
   audit**.

**Checkpoint:** both submissions show as pending in their developer consoles.
Write today's date somewhere. Now carry on — you will not touch either again
until they come back.

> Keep the App ID/Secret and Client Key/Secret somewhere safe now. You will
> paste them in Phase 4.

---

## Phase 1 — Running locally

*~1 hour. Needs no platform credentials at all.*

**Prerequisites:** Node 22+, pnpm 10+, PostgreSQL 16, Redis, and FFmpeg built
with `libx264` and `aac`.

```bash
ffmpeg -encoders | grep -E 'libx264|aac'   # must return matches
```

```bash
git clone https://github.com/themodernmanmedia/Automationsystemmedia.git
cd Automationsystemmedia
git checkout claude/modern-man-os-build-0xw5gn
pnpm install

cp .env.example .env
openssl rand -base64 32    # paste as ENCRYPTION_KEY
openssl rand -base64 32    # paste as SESSION_SECRET
# set DATABASE_URL and REDIS_URL to your local instances
```

> `ENCRYPTION_KEY` encrypts every platform token at rest. **Lose it and every
> connected account must be reconnected** — the ciphertext is unrecoverable.
> Put it in a password manager before you continue.

```bash
pnpm db:migrate

pnpm dev:api        # :4000
pnpm dev:worker     # separate terminal
pnpm dev:web        # separate terminal — :3000
```

Open <http://localhost:3000>, register the first account, then:

```bash
pnpm db:seed        # after registering — it needs the organization to exist
```

Registration is single-use by design: it creates the one organization and its
owner, then closes. Nobody can register into your system afterwards; further
users are invited by an admin.

**Checkpoint:**

```bash
curl -s localhost:4000/api/health | python3 -m json.tool
```

`"status": "healthy"` with both `database` and `queue` reporting `ok: true`. A
503 here names the failing dependency — fix that before going on. The
**Capabilities** page in the dashboard should load and show every integration as
unconfigured, which is correct at this point.

---

## Phase 2 — Decide whether the writing is good enough

*~1 hour. Needs only an LLM key. This is the real decision gate.*

This phase costs a few dollars and answers the only question that matters before
you spend weeks on platform integration: **is the content worth publishing?**

```bash
ANTHROPIC_API_KEY=sk-ant-...
RSS_FEEDS=https://feeds.bbci.co.uk/news/business/rss.xml,https://techcrunch.com/feed/
```

Choose feeds your audience actually cares about. The system can only write about
what it reads, and generic feeds produce generic content. Restart the API and
worker so they pick up the new values.

Then, on the **Automation** page, press **Run now → tick**, and watch the worker
log. A manual run ignores the hourly scan throttle and always ends with a `tick
complete` line saying what it did or why it had nothing to do.

**Checkpoint:** topics appear on the **Topics** page with scores, and after a
few minutes a piece appears on the **Content** page. Then do the part that
cannot be automated: **read it.** Read the hook, the carousel body, the caption.

- If it reads like your brand — go on.
- If it reads generic — that is a **brand configuration** problem, not a code
  problem. Edit tone, avoid-list and visual direction on the **Brand** page and
  run another tick. Fix it here, where a bad result costs a dollar, not after
  you are live.
- If it produces nothing — read `docs/TROUBLESHOOTING.md § Nothing is being
  generated`. The most common cause is feeds returning 403, which the worker log
  names explicitly.

Check `GET /api/cost` to see what a cycle actually costs you. Tune
`DAILY_COST_LIMIT_USD` from a real number rather than a guess.

> Nothing is published in this phase. Generation stops at `APPROVED`, and
> `AUTONOMOUS_MODE` is still `false`.

---

## Phase 3 — Object storage

*~30 minutes. Required before Instagram can publish anything.*

Meta **fetches** media from a public URL — you cannot upload bytes to it. So
publicly-readable, internet-resolvable storage is a hard requirement, not a
preference. Cloudflare R2 is the cheapest sane default because egress is free
and Meta will fetch every image you publish.

```bash
S3_ENDPOINT=https://<account>.r2.cloudflarestorage.com
S3_REGION=auto
S3_BUCKET=modernman-media
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_PUBLIC_BASE_URL=https://media.your-domain.com
```

**Checkpoint:** `S3_PUBLIC_BASE_URL` resolves from the public internet — test it
from your phone on mobile data, not from the machine running the system. A
localhost or private-network URL fails every publish, and the system rejects it
up front rather than letting the Meta call fail confusingly.

`/api/health` should now show `storage: true` under integrations.

---

## Phase 4 — Connect the accounts

*~30 minutes. Does **not** require App Review to have passed.*

While your Meta app is in development mode, anyone with a **role on the app**
can still authorize it. That is enough to connect your own accounts and test the
entire publishing path end to end.

```bash
META_APP_ID=...
META_APP_SECRET=...
META_REDIRECT_URI=https://your-domain.com/api/oauth/meta/callback

TIKTOK_CLIENT_KEY=...
TIKTOK_CLIENT_SECRET=...
TIKTOK_REDIRECT_URI=https://your-domain.com/api/oauth/tiktok/callback
```

The redirect URI must match **exactly** what you registered — no wildcards, and
HTTPS in production. Restart the API, then connect each account from the
**Accounts** page.

**Checkpoint:** each account shows `CONNECTED` with a token expiry date.
Instagram and Facebook are separate rows even though one Meta app covers both,
because publishing uses the Page's own token rather than your user token.

TikTok will show **AUDIT PENDING** until its audit passes. That label is
accurate and important: automation works completely, but every post is forced
to `SELF_ONLY` (private) regardless of what you request. When the audit clears,
mark the account audited:

```bash
curl -X PATCH https://your-domain.com/api/accounts/<id> \
  -H 'content-type: application/json' \
  -d '{"isAudited": true}'
```

---

## Phase 5 — The first post, published by hand

*~30 minutes. Do this before enabling autonomy. Once.*

Take one piece you have read and approved, and push it through the real
publishing path yourself:

```bash
# Approve it (or use the Approve button on the Content page)
curl -X POST .../api/content/<id>/approve

# Schedule it to specific accounts
curl -X POST .../api/content/<id>/schedule \
  -H 'content-type: application/json' \
  -d '{"socialAccountIds":["<account-id>"],"scheduledAt":"2026-09-10T17:00:00Z"}'
```

**Checkpoint:** the post appears on the platform. Then check the **Logs** page —
the publishing attempt should be recorded with the platform's own response, and
analytics should begin appearing within a day.

Two things to understand about scheduling, because they change what "scheduled"
means per platform:

- **Facebook** schedules natively. Once handed over, Facebook holds it. Your
  worker can be down and the post still goes out.
- **Instagram and TikTok cannot schedule.** Their APIs accept no future
  timestamp. This system holds those posts and publishes them itself at the
  target moment, which means **the worker must be running then.** The Calendar
  page marks which upcoming posts are self-timed for exactly this reason.

If publishing fails, the **Logs** page shows the platform's own error, and
`POST /api/automation/publishing/retry` requeues failures — deliberately
skipping authentication failures, since retrying a dead token only burns rate
limit and can never succeed.

---

## Phase 6 — Hand over the controls

*Only after Phases 1–5 all passed, and only when you have read enough output to
trust it.*

```bash
curl -X POST .../api/automation/autonomous \
  -H 'content-type: application/json' -d '{"enabled": true}'
```

Or the toggle on the **Automation** page. It refuses to enable without a working
LLM provider rather than looking enabled while producing only errors.

**Checkpoint — first week, daily:**

| Check | Where | What is wrong if not |
| --- | --- | --- |
| Anything in the exception queue | Content → Flagged | A QA gate is mistuned, or the brand config needs work |
| Failed agent runs | Logs | Read the error code; the log names the stage |
| Spend against limit | `/api/cost` | Adjust `DAILY_COST_LIMIT_USD` |
| Queue depth | Automation | `CRITICAL` for days means generation is failing quietly |
| Posts actually appearing | The platforms themselves | Not the dashboard — the platform |

Read every piece before it publishes for at least the first week. The system is
built to make that easy, not to make it unnecessary.

**The stop button**, which you should try once now so you know it works:

```bash
curl -X POST .../api/automation/kill \
  -H 'content-type: application/json' -d '{"engaged": true}'
```

The kill switch is checked at the start of every scheduled task, so it stops the
system everywhere rather than only at the API. It outranks a manual run — one
operator stopping the system cannot be overridden by another pressing a button.

---

## Phase 7 — Production

See `docs/DEPLOYMENT.md`. Three things that matter more than the rest:

1. **The worker must stay up continuously.** Instagram and TikTok posts are
   self-timed. A worker that is down at the target minute means a post that does
   not go out.
2. **Point your load balancer at `/api/health`.** It returns 200 only when both
   Postgres and Redis answer, and 503 with the specific reason otherwise.
3. **`ENCRYPTION_KEY` lives in a secret manager**, not in a file on the box, and
   it is backed up. Losing it means reconnecting every account.

---

## Realistic timeline

| Day | Do |
| --- | --- |
| 1 | Phase 0 — submit both applications. Phase 1 — running locally. |
| 2–3 | Phase 2 — read the output, tune the brand until it sounds like you. |
| 4 | Phase 3 — storage. Phase 4 — connect your own accounts. |
| 5 | Phase 5 — first post by hand. |
| Week 2+ | Phase 6 — autonomy, watched daily. |
| When Meta returns | Publishing to accounts beyond your own. |
| When TikTok returns | TikTok posts become publicly visible. |

The critical path is Meta App Review and the TikTok audit — which is exactly why
Phase 0 is first. Everything else fits inside that wait.
