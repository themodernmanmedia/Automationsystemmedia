# The Modern Man OS

An autonomous AI media operating system: it discovers topics, researches them
against citable sources, verifies the claims, writes and designs the content,
quality-checks it, schedules it, publishes it through **official platform APIs
only**, collects analytics, and feeds measured performance back into the scoring
that picks the next topic.

**Read `docs/API_LIMITATIONS.md` before anything else.** It is an honest account
of what the platforms genuinely do and do not permit. Nothing in this system
fakes an integration, fabricates a metric, or shows a button that cannot work.

## Documentation

| Document | What it covers |
| --- | --- |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design and the reasoning behind each decision |
| [`docs/platform-capabilities.md`](docs/platform-capabilities.md) | Per-platform capability matrix |
| [`docs/API_LIMITATIONS.md`](docs/API_LIMITATIONS.md) | What cannot be automated, and why |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Threat model and controls |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | **Start here.** Empty `.env` to first live post, in order |
| [`docs/PLATFORM_SETUP.md`](docs/PLATFORM_SETUP.md) | Obtaining the credentials, step by step |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Running it in production |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Diagnosing common failures |

## Three facts that shape the whole system

1. **Instagram and TikTok cannot schedule.** Neither API accepts a future
   timestamp, so this system owns a durable scheduler. Facebook *can* schedule
   natively, so the scheduler delegates to it. One interface, two strategies,
   chosen from a capability registry at runtime.
2. **Instagram fetches media from a public URL.** You cannot upload bytes to
   Meta. S3-compatible storage is therefore a hard requirement, not an option.
3. **TikTok forces every post from an unaudited app to be private.** Automation
   works end-to-end from day one, but nobody else can see the posts until your
   app passes TikTok's audit.

## Repository layout

```
apps/
  api/        Fastify API — auth, OAuth, content, publishing, automation control
  worker/     BullMQ workers, scheduler, and the autonomous loop
  web/        Next.js dashboard
packages/
  core/       Config, typed errors, crypto, logging, retry, rate limiting
  db/         Prisma schema and the tenant-scoped data layer
  platforms/  PlatformAdapter interface, capability registry, platform adapters
  ai/         Provider-agnostic LLM / image / voice / search / storage interfaces
  agents/     The research, content, and QA agents
  media/      Carousel slide renderer and the FFmpeg reel compositor
  engine/     Publishing, scheduling strategy, analytics, cost, kill switch
  contracts/  Zod schemas and the content lifecycle state machine
```

## What runs unattended

```
trend scan → topic scoring → research → fact check
    → strategy → hook → write → design → render
        → safety · brand · platform · rights · duplicate gates
            → APPROVED → scheduled → published → analytics → learning
                    ↘ FLAGGED (exception queue, waits for a human)
```

Every gate is enforced in code, not asked for in a prompt. In autonomous mode
only claims that survived fact-checking can reach a published asset, and
anything the system is not confident about leaves the automated path instead of
shipping.

## Running it without installing anything

Open the repository on GitHub → **Code ▾ → Codespaces → Create codespace**. The
devcontainer brings up Node 22, Postgres 16, Redis 7, FFmpeg and Chromium,
installs dependencies, generates real `ENCRYPTION_KEY` and `SESSION_SECRET`
values, and migrates the database. You land where Phase 1 of the runbook ends;
add an LLM key to `.env` and carry on from Phase 2.

**A Codespace is for building and evaluating, not for running the system.** It
stops when you stop using it, and Instagram and TikTok posts are self-timed by
this worker rather than held by the platform — so a scheduled post whose moment
arrives while the Codespace is asleep does not go out. Production belongs on a
host that stays up (`docs/DEPLOYMENT.md`).

## Quick start

```bash
pnpm install
cp .env.example .env          # then fill it in — see docs/PLATFORM_SETUP.md
openssl rand -base64 32       # ENCRYPTION_KEY
openssl rand -base64 32       # SESSION_SECRET

pnpm db:migrate

pnpm dev:api                  # :4000
pnpm dev:worker
pnpm dev:web                  # :3000
```

Then open <http://localhost:3000>, register the first account, and seed the
default brand:

```bash
pnpm db:seed                  # after registering — it seeds the brand for the
                              # organization that registration created
```

Registration is single-use: it creates the one organization and its `OWNER`, and
is closed afterwards. Seeding before that point exits with an error telling you
so, because a brand has to belong to an organization.

The `.env` lives at the repository root and is loaded by all three processes,
the Prisma CLI and the test suite. A real environment variable always wins over
it, so a deployment that injects configuration is unaffected by a file left in
the checkout.

Minimum to boot: Postgres, Redis, `ENCRYPTION_KEY`, `SESSION_SECRET`, and one
LLM API key. Add `RSS_FEEDS` (no API key needed) to give it something to
research. Platform credentials and S3 are needed to actually publish; the
dashboard reports precisely which integrations are configured and which are not.

## Testing

The suite exercises real Postgres and Redis, and the API tests truncate every
table (registration is single-use, so they have to start from zero
organizations). It therefore refuses to run against a database whose name does
not say `test`, rather than risk destroying a development dataset:

```bash
createdb mmos_test
echo 'DATABASE_URL=postgresql://mmos:mmos@localhost:5432/mmos_test?schema=public' > .env.test
DATABASE_URL=postgresql://mmos:mmos@localhost:5432/mmos_test?schema=public pnpm db:migrate

pnpm test
```

Every platform API is mocked with `nock`. The test setup blocks outbound network
access and fails the suite if a test attempts to contact a real platform host —
no test ever touches a production social account.

The media tests produce real files and inspect them: slides are verified as
genuine JPEGs at Instagram's 1080×1350, and composed videos are probed with
`ffprobe` to confirm H.264, 1080×1920, `yuv420p`, and an AAC audio stream.
They need FFmpeg with `libx264` and `aac`.
