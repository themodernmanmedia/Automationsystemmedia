import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { loadDotEnv } from './config.js';

const dirs: string[] = [];
const KEYS = ['MMOS_TEST_A', 'MMOS_TEST_B', 'MMOS_TEST_QUOTED'];

function workspace(files: Record<string, string>): string {
  const root = mkdtempSync(join(tmpdir(), 'mmos-env-'));
  dirs.push(root);
  writeFileSync(join(root, 'pnpm-workspace.yaml'), "packages:\n  - 'packages/*'\n");
  for (const [name, content] of Object.entries(files)) writeFileSync(join(root, name), content);
  const nested = join(root, 'apps', 'api');
  mkdirSync(nested, { recursive: true });
  return nested;
}

afterEach(() => {
  for (const key of KEYS) delete process.env[key];
  for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

describe('loadDotEnv', () => {
  it('finds the root .env from a nested working directory', () => {
    // This is the whole point: the apps run from apps/api, apps/worker and
    // packages/db, but the .env lives at the repository root.
    const nested = workspace({ '.env': 'MMOS_TEST_A=from-root\n' });
    const found = loadDotEnv(nested);
    expect(found).toBeDefined();
    expect(process.env['MMOS_TEST_A']).toBe('from-root');
  });

  it('never overrides a variable that is already set', () => {
    // Production and CI inject real values; a stale checkout .env must not win.
    process.env['MMOS_TEST_A'] = 'from-environment';
    const nested = workspace({ '.env': 'MMOS_TEST_A=from-file\nMMOS_TEST_B=only-in-file\n' });
    loadDotEnv(nested);
    expect(process.env['MMOS_TEST_A']).toBe('from-environment');
    expect(process.env['MMOS_TEST_B']).toBe('only-in-file');
  });

  it('prefers an earlier filename when several are offered', () => {
    const nested = workspace({
      '.env': 'MMOS_TEST_A=production-db\n',
      '.env.test': 'MMOS_TEST_A=throwaway-db\n',
    });
    loadDotEnv(nested, ['.env.test', '.env']);
    expect(process.env['MMOS_TEST_A']).toBe('throwaway-db');
  });

  it('falls back to the next filename when the first is absent', () => {
    const nested = workspace({ '.env': 'MMOS_TEST_A=only-plain\n' });
    loadDotEnv(nested, ['.env.test', '.env']);
    expect(process.env['MMOS_TEST_A']).toBe('only-plain');
  });

  it('is not an error when no file exists', () => {
    const nested = workspace({});
    expect(loadDotEnv(nested)).toBeUndefined();
  });

  it('stops at the workspace root rather than walking the whole filesystem', () => {
    // A stray .env in a parent directory of the checkout must not leak in.
    const nested = workspace({});
    loadDotEnv(nested);
    expect(process.env['MMOS_TEST_A']).toBeUndefined();
  });

  it('handles quoted values, using Node’s own parser', () => {
    const nested = workspace({ '.env': 'MMOS_TEST_QUOTED="a value with spaces"\n' });
    loadDotEnv(nested);
    expect(process.env['MMOS_TEST_QUOTED']).toBe('a value with spaces');
  });
});
