/**
 * Environment configuration.
 *
 * Parsed and validated once at boot with Zod. The app refuses to start on a bad
 * config rather than failing later inside a worker at 3am — a missing
 * ENCRYPTION_KEY discovered during a publish is far more expensive than one
 * discovered during startup.
 */
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { z } from 'zod';

/**
 * Loads the repository's root `.env` into `process.env`.
 *
 * Every entry point calls this before reading config. Without it nothing does:
 * the apps run from `apps/api`, `apps/worker` and `packages/db`, so a `.env`
 * at the repository root — which is where the quickstart puts it, and the only
 * sensible place for one shared by three processes — is never seen, and the
 * documented setup fails at the first command.
 *
 * Two deliberate properties:
 *
 * - **A real environment variable always wins.** In production, staging and CI
 *   the values come from the platform, and a stale `.env` left in a checkout
 *   must not silently override them. Node's own parser does the reading, so
 *   quoting and escapes behave as expected, and anything already set is then
 *   restored over the top.
 * - **A missing file is not an error.** Deployments that inject configuration
 *   directly have no `.env`, and refusing to boot without one would be wrong.
 *   Config validation still fails loudly if the values themselves are absent.
 */
export function loadDotEnv(
  startDir: string = process.cwd(),
  filenames: readonly string[] = ['.env'],
): string | undefined {
  let dir = resolve(startDir);
  for (;;) {
    // The workspace root is the boundary: stop there whether or not a file was
    // found, so a stray `.env` further up the filesystem cannot leak in.
    const isWorkspaceRoot = existsSync(join(dir, 'pnpm-workspace.yaml'));

    for (const filename of filenames) {
      const candidate = join(dir, filename);
      if (!existsSync(candidate)) continue;
      const preexisting = { ...process.env };
      try {
        process.loadEnvFile(candidate);
      } catch {
        return undefined; // Unreadable or malformed: config validation reports it.
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

const PLACEHOLDER_SECRETS = new Set([
  'changeme',
  'change-me',
  'secret',
  'password',
  'your-secret-here',
  'replace-me',
  'todo',
]);

/** A secret must be long enough to be real and must not be a known placeholder. */
const strongSecret = (name: string) =>
  z
    .string()
    .min(32, `${name} must be at least 32 characters`)
    .refine((v) => !PLACEHOLDER_SECRETS.has(v.toLowerCase().trim()), {
      message: `${name} is set to a placeholder value. Generate a real one: openssl rand -base64 32`,
    });

const csv = z
  .string()
  .optional()
  .transform((v) =>
    (v ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  );

const bool = z
  .string()
  .optional()
  .transform((v) => v === 'true' || v === '1');

const num = (fallback: number) =>
  z
    .string()
    .optional()
    .transform((v) => (v === undefined || v === '' ? fallback : Number(v)))
    .pipe(z.number().finite());

export const configSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'staging', 'production']).default('development'),
  LOG_LEVEL: z.enum(['trace', 'debug', 'info', 'warn', 'error', 'fatal', 'silent']).default('info'),
  API_PORT: num(4000),
  API_BASE_URL: z.string().url().default('http://localhost:4000'),
  WEB_BASE_URL: z.string().url().default('http://localhost:3000'),

  DATABASE_URL: z.string().min(1, 'DATABASE_URL is required'),
  REDIS_URL: z.string().min(1, 'REDIS_URL is required'),

  ENCRYPTION_KEY: strongSecret('ENCRYPTION_KEY'),
  SESSION_SECRET: strongSecret('SESSION_SECRET'),

  // Storage — required for Instagram, which fetches media from a public URL.
  S3_ENDPOINT: z.string().optional(),
  S3_REGION: z.string().default('auto'),
  S3_BUCKET: z.string().optional(),
  S3_ACCESS_KEY_ID: z.string().optional(),
  S3_SECRET_ACCESS_KEY: z.string().optional(),
  S3_PUBLIC_BASE_URL: z.string().optional(),

  LLM_PROVIDER: z.enum(['anthropic', 'openai']).default('anthropic'),
  ANTHROPIC_API_KEY: z.string().optional(),
  // The strongest model is the default, because nearly every call either
  // writes something that will be published under the brand's name or decides
  // whether something is safe to publish. The fast model is used only for the
  // high-volume ranking passes — see ModelTier in @mmos/ai.
  ANTHROPIC_MODEL: z.string().default('claude-opus-5'),
  ANTHROPIC_FAST_MODEL: z.string().default('claude-sonnet-5'),
  OPENAI_API_KEY: z.string().optional(),
  OPENAI_MODEL: z.string().default('gpt-4o'),
  OPENAI_FAST_MODEL: z.string().default('gpt-4o-mini'),

  IMAGE_PROVIDER: z.enum(['openai', 'stability', 'none']).default('none'),
  VOICE_PROVIDER: z.enum(['elevenlabs', 'openai', 'none']).default('none'),
  ELEVENLABS_API_KEY: z.string().optional(),
  ELEVENLABS_VOICE_ID: z.string().optional(),
  STABILITY_API_KEY: z.string().optional(),

  // Licensed stock imagery. Both licence for commercial use; both require
  // crediting the photographer under their API terms.
  UNSPLASH_ACCESS_KEY: z.string().optional(),
  PEXELS_API_KEY: z.string().optional(),

  SEARCH_PROVIDER: z.enum(['brave', 'tavily', 'none']).default('none'),
  BRAVE_SEARCH_API_KEY: z.string().optional(),
  TAVILY_API_KEY: z.string().optional(),
  NEWSAPI_KEY: z.string().optional(),
  RSS_FEEDS: csv,

  META_APP_ID: z.string().optional(),
  META_APP_SECRET: z.string().optional(),
  META_GRAPH_VERSION: z.string().default('v21.0'),
  META_REDIRECT_URI: z.string().optional(),

  TIKTOK_CLIENT_KEY: z.string().optional(),
  TIKTOK_CLIENT_SECRET: z.string().optional(),
  TIKTOK_REDIRECT_URI: z.string().optional(),

  FFMPEG_PATH: z.string().default('ffmpeg'),
  FFPROBE_PATH: z.string().default('ffprobe'),
  RENDER_WORK_DIR: z.string().default('./tmp/renders'),

  AUTONOMOUS_MODE: bool,
  DAILY_COST_LIMIT_USD: num(25),
  MONTHLY_COST_LIMIT_USD: num(500),
  MAX_POSTS_PER_DAY: num(8),
  QUEUE_TARGET_HOURS: num(72),
  QUEUE_MIN_HOURS: num(24),
  QUEUE_MAX_HOURS: num(168),
});

export type Config = z.infer<typeof configSchema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const parsed = configSchema.safeParse(env);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  • ${i.path.join('.') || '(root)'}: ${i.message}`)
      .join('\n');
    throw new Error(
      `Invalid environment configuration:\n${issues}\n\nSee .env.example for the full list of variables.`,
    );
  }
  return parsed.data;
}

let cached: Config | undefined;
export function getConfig(): Config {
  cached ??= loadConfig();
  return cached;
}
/** Test-only: drop the memoized config so a suite can vary the environment. */
export function resetConfigCache(): void {
  cached = undefined;
}

/* ------------------------------------------------------------------ */
/* Capability probes — "is this part of the system actually usable?"   */
/* ------------------------------------------------------------------ */

/**
 * These let the API tell the dashboard the truth about what is wired up, so the
 * UI can disable a control and explain why instead of offering a button that
 * throws. This is the mechanism behind the "no fake automation" rule.
 */
export interface ConfiguredIntegrations {
  storage: boolean;
  llm: boolean;
  image: boolean;
  stock: boolean;
  voice: boolean;
  search: boolean;
  meta: boolean;
  tiktok: boolean;
}

export function configuredIntegrations(c: Config): ConfiguredIntegrations {
  return {
    storage: Boolean(c.S3_BUCKET && c.S3_ACCESS_KEY_ID && c.S3_SECRET_ACCESS_KEY && c.S3_PUBLIC_BASE_URL),
    llm:
      (c.LLM_PROVIDER === 'anthropic' && Boolean(c.ANTHROPIC_API_KEY)) ||
      (c.LLM_PROVIDER === 'openai' && Boolean(c.OPENAI_API_KEY)),
    image:
      (c.IMAGE_PROVIDER === 'openai' && Boolean(c.OPENAI_API_KEY)) ||
      (c.IMAGE_PROVIDER === 'stability' && Boolean(c.STABILITY_API_KEY)),
    stock: Boolean(c.UNSPLASH_ACCESS_KEY) || Boolean(c.PEXELS_API_KEY),
    voice:
      (c.VOICE_PROVIDER === 'elevenlabs' && Boolean(c.ELEVENLABS_API_KEY)) ||
      (c.VOICE_PROVIDER === 'openai' && Boolean(c.OPENAI_API_KEY)),
    search:
      (c.SEARCH_PROVIDER === 'brave' && Boolean(c.BRAVE_SEARCH_API_KEY)) ||
      (c.SEARCH_PROVIDER === 'tavily' && Boolean(c.TAVILY_API_KEY)) ||
      Boolean(c.NEWSAPI_KEY) ||
      c.RSS_FEEDS.length > 0,
    meta: Boolean(c.META_APP_ID && c.META_APP_SECRET && c.META_REDIRECT_URI),
    tiktok: Boolean(c.TIKTOK_CLIENT_KEY && c.TIKTOK_CLIENT_SECRET && c.TIKTOK_REDIRECT_URI),
  };
}
