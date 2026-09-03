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
  ai/         Provider-agnostic LLM / image / voice / search interfaces
  agents/     The research, content, media, and QA agents
  contracts/  Zod schemas and the content lifecycle state machine
```

## Quick start

```bash
pnpm install
cp .env.example .env          # then fill it in — see docs/PLATFORM_SETUP.md
openssl rand -base64 32       # ENCRYPTION_KEY
openssl rand -base64 32       # SESSION_SECRET

pnpm db:migrate
pnpm db:seed

pnpm dev:api                  # :4000
pnpm dev:worker
pnpm dev:web                  # :3000
```

Minimum to boot: Postgres, Redis, `ENCRYPTION_KEY`, `SESSION_SECRET`, and one
LLM API key. Platform credentials and S3 are needed to actually publish; the
dashboard reports precisely which integrations are configured and which are not.

## Testing

```bash
pnpm test
```

Every platform API is mocked with `nock`. The test setup blocks outbound network
access and fails the suite if a test attempts to contact a real platform host —
no test ever touches a production social account.
