# Node 22 is what the workspace requires; pnpm arrives via corepack in
# post-create.sh so the version stays pinned by package.json rather than here.
FROM mcr.microsoft.com/devcontainers/typescript-node:22

# FFmpeg is not optional: the reel compositor shells out to it, and the media
# tests probe real output with ffprobe. The client tools make it possible to
# inspect Postgres and Redis from the terminal while debugging a run.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg postgresql-client redis-tools \
 && rm -rf /var/lib/apt/lists/*
