// Next.js only reads a `.env` beside this config, but this system keeps one
// shared `.env` at the repository root for the API, the worker and the
// dashboard. Loading it here puts the values in `process.env` before the
// config below and before any server component reads them. A real environment
// variable still wins, so a deployment that injects config is unaffected.
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

function loadRootEnv(startDir) {
  let dir = resolve(startDir);
  for (;;) {
    const candidate = join(dir, '.env');
    const isWorkspaceRoot = existsSync(join(dir, 'pnpm-workspace.yaml'));
    if (existsSync(candidate)) {
      const preexisting = { ...process.env };
      try {
        process.loadEnvFile(candidate);
      } catch {
        return;
      }
      for (const [key, value] of Object.entries(preexisting)) {
        if (value !== undefined) process.env[key] = value;
      }
      return;
    }
    if (isWorkspaceRoot) return;
    const parent = dirname(dir);
    if (parent === dir) return;
    dir = parent;
  }
}

loadRootEnv(dirname(fileURLToPath(import.meta.url)));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emits apps/web/.next/standalone/server.js — the server DEPLOYMENT.md tells
  // you to run, and the only way to ship the dashboard without the whole
  // node_modules tree. Without this the documented production command has no
  // file to execute.
  output: 'standalone',
  // The workspace root, so tracing collects files from packages/* rather than
  // only apps/web.
  outputFileTracingRoot: resolve(dirname(fileURLToPath(import.meta.url)), '../..'),
  // The dashboard never talks to platform APIs directly; everything goes
  // through our API so credentials stay server-side.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_BASE_URL ?? 'http://localhost:4000'}/api/:path*`,
      },
    ];
  },
};
export default nextConfig;
