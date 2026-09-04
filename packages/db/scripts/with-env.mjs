#!/usr/bin/env node
/**
 * Runs the Prisma CLI with the repository's root `.env` loaded.
 *
 * pnpm runs a package's scripts with that package's directory as the working
 * directory, and Prisma only looks for `.env` beside the schema or in the
 * current directory — so `pnpm db:migrate` from the repository root never saw
 * a root `.env` and failed with "Environment variable not found: DATABASE_URL"
 * on any fresh clone.
 *
 * The loading logic is duplicated from `@mmos/core` rather than imported on
 * purpose: this has to work before anything is compiled, since `pnpm build`
 * itself begins by running `prisma generate` through here.
 */
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

function loadDotEnv(startDir) {
  let dir = resolve(startDir);
  for (;;) {
    const candidate = join(dir, '.env');
    const isWorkspaceRoot = existsSync(join(dir, 'pnpm-workspace.yaml'));
    if (existsSync(candidate)) {
      // A real environment variable always wins over the file.
      const preexisting = { ...process.env };
      try {
        process.loadEnvFile(candidate);
      } catch {
        return undefined;
      }
      for (const [key, value] of Object.entries(preexisting)) {
        if (value !== undefined) process.env[key] = value;
      }
      return candidate;
    }
    if (isWorkspaceRoot) return undefined;
    const parent = dirname(dir);
    if (parent === dir) return undefined;
    dir = parent;
  }
}

loadDotEnv(dirname(fileURLToPath(import.meta.url)));

const child = spawn('prisma', process.argv.slice(2), {
  stdio: 'inherit',
  shell: process.platform === 'win32',
});
child.on('exit', (code, signal) => process.exit(signal ? 1 : (code ?? 1)));
child.on('error', (err) => {
  console.error('Could not run the Prisma CLI:', err.message);
  process.exit(1);
});
