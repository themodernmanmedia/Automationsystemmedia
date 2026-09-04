import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { loadConfig } from './config.js';

/** `.env.example` as a plain object, exactly as `cp .env.example .env` leaves it. */
function envExample(): Record<string, string> {
  const path = resolve(import.meta.dirname, '../../../.env.example');
  const out: Record<string, string> = {};
  for (const line of readFileSync(path, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    // Strip the trailing `# comment` the example uses to document choices.
    out[trimmed.slice(0, eq)] = trimmed.slice(eq + 1).replace(/\s+#.*$/, '').trim();
  }
  return out;
}

describe('.env.example', () => {
  it('boots once the four required values are filled in', () => {
    // The regression this pins: `cp .env.example .env` produced a file the app
    // refused to start on. The optional providers ship as `KEY=`, and Zod's
    // `.default()` only applies to an ABSENT key, so three blank lines failed
    // validation and the error named providers the operator never asked for.
    const config = loadConfig({
      ...envExample(),
      DATABASE_URL: 'postgresql://mmos:mmos@localhost:5432/mmos?schema=public',
      REDIS_URL: 'redis://localhost:6379',
      ENCRYPTION_KEY: Buffer.alloc(32, 7).toString('base64'),
      SESSION_SECRET: Buffer.alloc(32, 9).toString('base64'),
    } as NodeJS.ProcessEnv);

    expect(config.IMAGE_PROVIDER).toBe('none');
    expect(config.VOICE_PROVIDER).toBe('none');
    expect(config.SEARCH_PROVIDER).toBe('none');
    expect(config.LLM_PROVIDER).toBe('anthropic');
    // Autonomous mode must never be on by default.
    expect(config.AUTONOMOUS_MODE).toBe(false);
  });

  it('treats a blank optional enum as unset rather than invalid', () => {
    const base = {
      DATABASE_URL: 'postgresql://localhost:5432/x',
      REDIS_URL: 'redis://localhost:6379',
      ENCRYPTION_KEY: Buffer.alloc(32, 7).toString('base64'),
      SESSION_SECRET: Buffer.alloc(32, 9).toString('base64'),
    };
    const config = loadConfig({
      ...base,
      IMAGE_PROVIDER: '',
      VOICE_PROVIDER: '  ',
      SEARCH_PROVIDER: '',
      LOG_LEVEL: '',
    } as NodeJS.ProcessEnv);

    expect(config.IMAGE_PROVIDER).toBe('none');
    expect(config.VOICE_PROVIDER).toBe('none');
    expect(config.LOG_LEVEL).toBe('info');
  });

  it('still rejects a value that is wrong rather than blank', () => {
    // Forgiving a blank must not mean forgiving a typo — that would boot with a
    // provider the operator thought they had configured.
    expect(() =>
      loadConfig({
        DATABASE_URL: 'postgresql://localhost:5432/x',
        REDIS_URL: 'redis://localhost:6379',
        ENCRYPTION_KEY: Buffer.alloc(32, 7).toString('base64'),
        SESSION_SECRET: Buffer.alloc(32, 9).toString('base64'),
        IMAGE_PROVIDER: 'dall-e',
      } as NodeJS.ProcessEnv),
    ).toThrow(/IMAGE_PROVIDER/);
  });

  it('refuses a placeholder secret', () => {
    expect(() =>
      loadConfig({
        DATABASE_URL: 'postgresql://localhost:5432/x',
        REDIS_URL: 'redis://localhost:6379',
        ENCRYPTION_KEY: 'changeme',
        SESSION_SECRET: Buffer.alloc(32, 9).toString('base64'),
      } as NodeJS.ProcessEnv),
    ).toThrow(/ENCRYPTION_KEY/);
  });
});
