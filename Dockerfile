# syntax=docker/dockerfile:1
#
# One image, three commands. The API, the worker and the dashboard share a
# build; the process is chosen by the command the host runs, so there is no way
# for them to drift to different versions of the same code.
#
# The image carries FFmpeg and Chromium because the worker genuinely needs both:
# it composes real video and renders carousel slides in a real browser. That
# makes it larger than a plain Node image, and shipping a worker that cannot
# render would be the wrong trade.

# ---------------------------------------------------------------- build ----
FROM node:22-bookworm-slim AS build

# Prisma's query engine links against OpenSSL at build and at run time.
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN corepack enable
WORKDIR /app

# Playwright is a dependency, but the browser comes from the distribution
# instead — one Chromium in the image rather than two.
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Build-time only. `prisma generate` validates a schema that reads this, and
# nothing connects during the build. The real value arrives from the host's
# environment at run time and overrides it.
ENV DATABASE_URL=postgresql://build:build@127.0.0.1:5432/build

COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm db:generate
RUN pnpm build

# Next's standalone output deliberately excludes static assets and public
# files; they have to be placed beside the server or every page loads without
# its CSS.
RUN cp -r apps/web/.next/static apps/web/.next/standalone/apps/web/.next/static \
 && if [ -d apps/web/public ]; then cp -r apps/web/public apps/web/.next/standalone/apps/web/public; fi

# -------------------------------------------------------------- runtime ----
FROM node:22-bookworm-slim AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ffmpeg \
      chromium \
      fonts-liberation \
      openssl \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN corepack enable
WORKDIR /app

ENV NODE_ENV=production \
    FFMPEG_PATH=/usr/bin/ffmpeg \
    FFPROBE_PATH=/usr/bin/ffprobe \
    CHROMIUM_PATH=/usr/bin/chromium \
    RENDER_WORK_DIR=/tmp/renders

COPY --from=build --chown=node:node /app /app
RUN mkdir -p /tmp/renders && chown node:node /tmp/renders

USER node
EXPOSE 4000 3000

# Overridden per service. The API is the default because it is the one that
# answers a health check.
CMD ["node", "apps/api/dist/server.js"]
