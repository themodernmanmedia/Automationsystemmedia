# Deployment

## Shape

Three processes, one database, one Redis, one bucket:

```
web (Next.js)  →  api (Fastify)  →  Postgres
                        ↑              ↑
                     worker  ─────────┘
                        ↓
                 Redis + S3 storage
```

**The worker is not optional.** Instagram and TikTok have no scheduling API, so
the worker *is* the scheduler. If it is down at a post's scheduled time, that
post goes out late — the reconciler catches up on boot, but it cannot go back in
time. Run it with a restart policy and alert on it.

## Environments

Keep three, with separate databases and separate Meta/TikTok apps:

| | Purpose |
| --- | --- |
| development | Local. Autonomous mode off. |
| staging | A throwaway IG/TikTok account. Never the real brand. |
| production | The real accounts. |

Never point staging at a production social account. A bad generation cycle
publishing to your real audience is not recoverable — Instagram's API cannot
even delete what it published.

## Database migrations

```bash
pnpm db:generate
pnpm db:migrate      # prisma migrate deploy — no shadow DB, no CREATEDB needed
```

Run migrations before starting the new API and worker. The production database
user needs no `CREATEDB` or `SUPERUSER`; only local `migrate dev` does.

## Process configuration

```bash
# api
NODE_ENV=production
API_PORT=4000
node apps/api/dist/server.js

# worker — the scheduler. Restart on failure.
node apps/worker/dist/index.js

# web
node apps/web/.next/standalone/server.js
```

Scale the API horizontally as needed. **Run exactly one worker** unless you
shard by organization: BullMQ locks jobs so duplicates are not published, but a
second worker adds no throughput at this volume and complicates reasoning about
the loop.

## Health checks

- API: `GET /api/health` → 200 healthy, 503 degraded. It also reports which
  integrations are configured, which is the fastest way to diagnose "why is
  nothing generating".
- Worker: it logs `worker ready` on boot and `reconciled scheduled publishing
  jobs` every 30 minutes. Alert if that line stops appearing.

## What to alert on

| Signal | Why it matters |
| --- | --- |
| Worker process down | Scheduled Instagram/TikTok posts will be late |
| `overdue` > 0 in the reconcile log | The worker was down at a scheduled time |
| Account status `TOKEN_EXPIRED` | Publishing to that account is broken until reconnected |
| Publishing jobs in `FAILED` | Something is genuinely wrong; retries are exhausted |
| Daily cost approaching the limit | Generation is about to halt |
| Content in `FLAGGED` accumulating | The exception queue needs a human |

TikTok access tokens last only ~24 hours. The hourly refresh job handles this,
but if the worker is down for a day, TikTok will need reconnecting.

## Backups

Back up Postgres. **Redis needs no backup** — it holds only job timers, and the
reconciler rebuilds them from Postgres on boot. That is the entire reason the
scheduler is designed this way.

Back up `ENCRYPTION_KEY` separately and securely. Losing it means every
connected account must be reconnected.

## Secrets

Use your platform's secret manager. Never commit `.env`. The application
refuses to boot when `ENCRYPTION_KEY` or `SESSION_SECRET` is missing, too short,
or a known placeholder — that check is intentional, so do not work around it.

## Rollback

The application is stateless apart from Postgres. To roll back, deploy the
previous image; migrations are additive, so an older application generally runs
against a newer schema. If a release is misbehaving in a way that could publish
bad content, **engage the kill switch first** (`POST /api/automation/kill`), then
roll back. Stopping output matters more than a clean deploy.

## Health checks

`GET /api/health` returns 200 only when both Postgres and Redis answer;
otherwise 503 with `status: "degraded"` and a per-check reason. Point the load
balancer at it.

The Redis probe is raced against a 2-second timeout. BullMQ requires
`maxRetriesPerRequest: null` on its connection, which makes ioredis queue
commands indefinitely against an unreachable server instead of failing them —
so an unraced probe would hang, and an orchestrator would read that timeout as
a dead container and restart a service that was only missing its queue.
