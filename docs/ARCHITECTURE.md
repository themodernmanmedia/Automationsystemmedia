# The Modern Man OS — Architecture

## 1. What this system is

An autonomous content operating system for a single media brand (extensible to many).
It discovers topics, researches them against citable sources, verifies claims, writes
and designs content, quality-checks it, schedules it, publishes it through **official
platform APIs only**, collects analytics, and feeds measured performance back into the
scoring functions that pick the next topic.

## 2. The constraint that shapes everything

**Instagram and TikTok have no native scheduling.** A "scheduled post" is our own
durable scheduler waking at the target time and firing the publish call. Facebook Pages
*does* schedule natively. So scheduling is not one behavior — it is a per-platform
strategy selected from a capability registry at runtime:

```
DELEGATED   → hand the timestamp to the platform (Facebook)
SELF_TIMED  → persist intent, wake ourselves, publish then (Instagram, TikTok)
```

This is why `PlatformAdapter` exposes `getPublishingCapabilities()` and why the
scheduler branches on it rather than assuming a uniform interface. The same registry
drives the dashboard, which renders `NOT SUPPORTED BY CURRENT API` for a capability
the adapter declares absent instead of showing a button that cannot work.

## 3. Stack decisions and why

| Layer | Choice | Rationale |
| --- | --- | --- |
| Language | TypeScript everywhere | One type system from Prisma row → API → React prop. The domain is heavily shaped by shared contracts; a second language buys nothing. |
| API | Fastify | Fast, first-class JSON-schema validation, cleanest plugin/lifecycle model for a service that is mostly typed request/response. |
| DB | PostgreSQL + Prisma | The domain is deeply relational (topic → claims → sources → content → slides → jobs → analytics) and the audit requirement means nothing may be denormalized away. |
| Queue | BullMQ on Redis | Mature delayed jobs, retries with backoff, and a real dead-letter path. |
| Scheduler | Postgres as source of truth, Redis as the timer | **Deliberate:** Redis is not durable enough to be the only record of "publish this at 09:00". A reconciler re-arms from Postgres on boot, so losing Redis loses timing precision, never the post. |
| Web | Next.js 15 App Router | Server components for data-heavy dashboard reads; one deploy target. |
| Storage | S3-compatible | **Required, not optional:** Meta pulls media from a public URL. Without externally-fetchable storage, Instagram publishing cannot work at all. |
| AI | Provider-agnostic interfaces | Per the brief. `LLMProvider` has real Anthropic and OpenAI implementations; media providers are interfaces with the implementations you configure. |

## 4. Topology

```
                    ┌──────────────┐
                    │  Next.js UI  │
                    └──────┬───────┘
                           │ HTTP (session cookie, CSRF)
                    ┌──────▼───────┐
                    │ Fastify API  │──── RBAC, rate limit, audit log
                    └──────┬───────┘
          ┌────────────────┼────────────────┐
     ┌────▼────┐     ┌─────▼─────┐    ┌─────▼─────┐
     │ Postgres│     │   Redis   │    │    S3     │
     └────┬────┘     └─────┬─────┘    └─────┬─────┘
          │                │                │
          │          ┌─────▼──────┐         │
          └──────────┤  Workers   ├─────────┘
                     └─────┬──────┘
                           │
                  ┌────────▼─────────┐
                  │  AI Orchestrator │  cost meter + budget gate
                  └────────┬─────────┘
              ┌────────────┼────────────┐
          research      content       media
           agents        agents       agents
              └────────────┼────────────┘
                     quality control
                  (brand · platform · safety · rights · dedupe)
                           │
                   platform adapters
              ┌────────────┼────────────┐
          Instagram      TikTok      Facebook
                           │
                       analytics
                           │
                    learning engine  ──▶ updates scoring weights
                           │
                    back to topic selection
```

## 5. Content lifecycle

Every `ContentPiece` moves through an explicit, persisted state machine. Illegal
transitions throw; every transition writes an `AuditLog` row.

```
DISCOVERED → RESEARCHING → RESEARCHED → WRITING → DESIGNING
   → QA → APPROVED → SCHEDULED → PUBLISHING → PUBLISHED → ANALYZING → LEARNED
                ↘ FLAGGED (exception queue)  ↘ FAILED  ↘ ARCHIVED
```

`FLAGGED` is the pressure-release valve that makes autonomous mode safe: anything the
system is not confident about leaves the automated path instead of shipping.

## 6. The fact gate

The brief asks for autonomy; autonomy without a fact gate is a machine for publishing
confident falsehoods under your brand name. So:

- Every factual claim is a first-class `Claim` row with `sourceUrl`, `sourceDate`,
  `retrievedAt`, and `confidence`. Claims are extracted from fetched sources, never
  from model memory.
- The fact checker labels each `VERIFIED | PARTIALLY_VERIFIED | UNVERIFIED | CONTRADICTED`.
- In autonomous mode **only `VERIFIED` claims may reach a published asset.** Others are
  dropped, softened, or the whole piece is `FLAGGED`. This is enforced in the QA
  pipeline, not left to prompt discipline.

## 7. Cost control

Every LLM/image/video/voice call goes through the orchestrator, which records tokens and
computed cost against a `CostEntry` attributed to a topic and content piece. A budget
gate checks the rolling daily/monthly spend **before** dispatching a call and throws
`BudgetExceededError` rather than silently draining a card. Generation is the expensive
part of this product; it is metered from day one, not bolted on.

## 8. Learning engine

Not a black box. It computes per-dimension performance aggregates (category, format,
hook archetype, slide count, reel length, posting hour) from normalized analytics, then
adjusts the **topic-scoring weights** and **format allocation** that drive the next
cycle. Adjustments are bounded (no weight may move more than a configured step per
cycle) and every change is written to `AgentRun` so a bad week is explainable and
reversible. Sample-size floors prevent three lucky posts from rewriting strategy.

## 9. Security posture

- Platform tokens are encrypted at rest with AES-256-GCM (`packages/core/src/crypto.ts`)
  under a key from the environment; ciphertext is versioned so keys can be rotated.
- Tokens never cross the API boundary to the browser. The dashboard sees status and
  expiry, never material.
- Session cookies are `httpOnly`, `sameSite=lax`, `secure` outside dev; state-changing
  routes require a CSRF token; OAuth uses a signed, single-use `state`.
- RBAC: `OWNER | ADMIN | EDITOR | VIEWER`, enforced per route.
- Every privileged action writes an immutable `AuditLog` row.

See `docs/SECURITY.md`.

## 10. Kill switch

`POST /automation/kill` sets a global flag checked by every worker at job start and
before every publish, drains the delayed queues, and stops the schedulers. It is
deliberately the simplest code path in the system — a stop control that depends on
subtle logic is not a stop control. `PAUSE ALL`, `STOP PUBLISHING`, `DISABLE AGENT`,
`CLEAR QUEUE` and `DISCONNECT ACCOUNT` are separate, independently effective controls.

## Model tiers

Two tiers, not one model. The default is the strongest model available, because
almost every call either writes text that will be published under the brand's
name or decides whether something is safe to publish — neither is worth
economising on, and a weaker model shows up as blander hooks and softer safety
judgements rather than as an error.

The `fast` tier is used for exactly two things: trend scanning, which ranks a
large batch of headlines, and topic scoring, which runs once per candidate
topic and is the highest-volume call in the system. Both are classification
against fixed criteria rather than writing, and running the strongest model
over every candidate would multiply cost without changing which topics win.

A tier is a request property (`tier: 'fast'`), resolved by the provider against
`ANTHROPIC_MODEL` / `ANTHROPIC_FAST_MODEL` (or the OpenAI pair). An explicit
`model` overrides it. Setting only the primary model makes everything use that
one, so nobody ends up with a second model they did not choose.

## 11. Honest limits

Collected in `docs/API_LIMITATIONS.md`. Summary: TikTok posts are private until your
app passes audit; Instagram cannot schedule, cannot delete API-published media, and has
withdrawn much of its analytics surface; there is no legitimate commercial trend feed
from any of the three platforms; and rendering finished video requires FFmpeg plus paid
media providers you must supply.
