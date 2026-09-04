#!/usr/bin/env bash
#
# Runs once when the container is created.
#
# The goal is that a Codespace comes up in the state Phase 1 of the runbook
# ends in: dependencies installed, database migrated, and a `.env` holding real
# generated secrets. It deliberately does NOT add any API key — there is none to
# add, and inventing one would produce a system that looks configured and fails
# at the first call.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Installing dependencies"
corepack enable
pnpm install --frozen-lockfile

echo "==> Installing Chromium for slide rendering"
# The carousel renderer drives headless Chromium; the media tests render real
# JPEGs through it.
pnpm exec playwright install --with-deps chromium

if [ ! -f .env ]; then
  echo "==> Writing .env with freshly generated secrets"
  # Generated per-Codespace, never committed and never a fixed value: a shared
  # ENCRYPTION_KEY would mean every checkout could decrypt every other one's
  # platform tokens.
  cp .env.example .env
  ENCRYPTION_KEY="$(openssl rand -base64 32)"
  SESSION_SECRET="$(openssl rand -base64 32)"
  python3 - "$ENCRYPTION_KEY" "$SESSION_SECRET" <<'PY'
import sys, pathlib
key, secret = sys.argv[1], sys.argv[2]
p = pathlib.Path('.env')
lines = []
for line in p.read_text().splitlines():
    if line.startswith('ENCRYPTION_KEY='):
        line = f'ENCRYPTION_KEY={key}'
    elif line.startswith('SESSION_SECRET='):
        line = f'SESSION_SECRET={secret}'
    elif line.startswith('DATABASE_URL='):
        line = 'DATABASE_URL=postgresql://mmos:mmos@db:5432/mmos?schema=public'
    elif line.startswith('REDIS_URL='):
        line = 'REDIS_URL=redis://redis:6379'
    elif line.startswith('FFMPEG_PATH='):
        line = 'FFMPEG_PATH=/usr/bin/ffmpeg'
    elif line.startswith('FFPROBE_PATH='):
        line = 'FFPROBE_PATH=/usr/bin/ffprobe'
    lines.append(line)
p.write_text('\n'.join(lines) + '\n')
PY
else
  echo "==> .env already present; leaving it alone"
fi

echo "==> Waiting for Postgres"
for _ in $(seq 1 30); do
  if pg_isready -h db -U mmos -q; then break; fi
  sleep 2
done

# The suite truncates every table, so it gets its own database and refuses to
# run against one whose name does not say "test".
if [ ! -f .env.test ]; then
  echo "==> Creating the test database"
  PGPASSWORD=mmos createdb -h db -U mmos mmos_test 2>/dev/null || true
  cat > .env.test <<'ENVTEST'
DATABASE_URL=postgresql://mmos:mmos@db:5432/mmos_test?schema=public
REDIS_URL=redis://redis:6379
ENVTEST
  DATABASE_URL='postgresql://mmos:mmos@db:5432/mmos_test?schema=public' pnpm db:migrate
fi

echo "==> Migrating the application database"
pnpm db:generate
pnpm db:migrate

cat <<'DONE'

  Ready.

    pnpm dev:api        :4000
    pnpm dev:worker
    pnpm dev:web        :3000   <- open this, register the first account
    pnpm db:seed        after registering

  Nothing can generate until you add an LLM key to .env:

    ANTHROPIC_API_KEY=sk-ant-...
    RSS_FEEDS=https://feeds.bbci.co.uk/news/business/rss.xml

  Then follow docs/RUNBOOK.md from Phase 2.

DONE
