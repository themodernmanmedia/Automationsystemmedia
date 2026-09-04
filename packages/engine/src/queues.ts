/**
 * Queue topology.
 *
 * BullMQ over Redis for timers and retries, with Postgres as the durable record
 * of intent. That split is deliberate: Redis is not a safe single home for
 * "publish this at 09:00", so losing Redis costs timing precision, never the
 * post — the reconciler re-arms every job from the database on boot.
 */
import { Queue, type JobsOptions } from 'bullmq';
import { Redis } from 'ioredis';

export const QUEUE_NAMES = {
  trendScan: 'trend-scan',
  topicScoring: 'topic-scoring',
  research: 'research',
  contentGeneration: 'content-generation',
  mediaGeneration: 'media-generation',
  qualityControl: 'quality-control',
  publishing: 'publishing',
  analytics: 'analytics',
  learning: 'learning',
  tokenRefresh: 'token-refresh',
  autonomousLoop: 'autonomous-loop',
} as const;

export type QueueName = (typeof QUEUE_NAMES)[keyof typeof QUEUE_NAMES];

export function createConnection(redisUrl: string): Redis {
  return new Redis(redisUrl, {
    // Required by BullMQ: it manages its own retry semantics, and capping
    // retries per request would make blocking commands fail spuriously.
    maxRetriesPerRequest: null,
    enableReadyCheck: false,
  });
}

/**
 * Default retry policy. Exponential backoff from 5s, and failures are retained
 * so the dashboard can explain what went wrong rather than showing a job that
 * vanished.
 */
export const DEFAULT_JOB_OPTIONS: JobsOptions = {
  attempts: 4,
  backoff: { type: 'exponential', delay: 5_000 },
  removeOnComplete: { count: 500, age: 7 * 86_400 },
  removeOnFail: { count: 1000, age: 30 * 86_400 },
};

/**
 * Publishing gets fewer attempts than other work. A publish that keeps failing
 * is usually an auth or media problem that retrying cannot fix, and each
 * attempt consumes platform rate limit.
 */
export const PUBLISH_JOB_OPTIONS: JobsOptions = {
  attempts: 3,
  backoff: { type: 'exponential', delay: 30_000 },
  removeOnComplete: { count: 1000, age: 30 * 86_400 },
  removeOnFail: false, // keep every failed publish for inspection
};

export class QueueRegistry {
  readonly #queues = new Map<QueueName, Queue>();
  readonly #connection: Redis;

  constructor(redisUrl: string) {
    this.#connection = createConnection(redisUrl);
    for (const name of Object.values(QUEUE_NAMES)) {
      this.#queues.set(name, new Queue(name, { connection: this.#connection, defaultJobOptions: DEFAULT_JOB_OPTIONS }));
    }
  }

  get(name: QueueName): Queue {
    const queue = this.#queues.get(name);
    if (!queue) throw new Error(`Unknown queue: ${name}`);
    return queue;
  }

  get connection(): Redis {
    return this.#connection;
  }

  /** Counts for the dashboard's automation panel. */
  async stats(): Promise<Record<string, { waiting: number; active: number; delayed: number; failed: number }>> {
    const result: Record<string, { waiting: number; active: number; delayed: number; failed: number }> = {};
    for (const [name, queue] of this.#queues) {
      const counts = await queue.getJobCounts('waiting', 'active', 'delayed', 'failed');
      result[name] = {
        waiting: counts['waiting'] ?? 0,
        active: counts['active'] ?? 0,
        delayed: counts['delayed'] ?? 0,
        failed: counts['failed'] ?? 0,
      };
    }
    return result;
  }

  /** Emergency control: drops every pending and delayed job. */
  async drainAll(): Promise<void> {
    for (const queue of this.#queues.values()) {
      await queue.drain(true);
    }
  }

  /**
   * Liveness probe for the health endpoint.
   *
   * Worth reporting separately from the database: the API deliberately starts
   * without Redis so a queue outage cannot take the whole service down, but
   * everything that publishes runs through it. Without this, a health check
   * would say "healthy" while nothing could be scheduled or published.
   */
  async healthcheck(timeoutMs = 2_000): Promise<{ ok: boolean; latencyMs: number; error?: string }> {
    const start = Date.now();
    try {
      // The ping MUST be raced against a timeout. BullMQ requires
      // `maxRetriesPerRequest: null` on its connection, which means ioredis
      // queues commands indefinitely while the server is unreachable rather
      // than failing them — so an unraced ping never settles, and the health
      // endpoint hangs instead of answering. A health check that hangs is
      // worse than one that is wrong: an orchestrator reads the timeout as a
      // dead container and restarts a service that was merely missing Redis.
      await Promise.race([
        this.#connection.ping(),
        new Promise((_resolve, reject) =>
          setTimeout(() => reject(new Error(`Redis did not respond within ${timeoutMs}ms`)), timeoutMs).unref(),
        ),
      ]);
      return { ok: true, latencyMs: Date.now() - start };
    } catch (err) {
      return { ok: false, latencyMs: Date.now() - start, error: (err as Error).message };
    }
  }

  async close(): Promise<void> {
    for (const queue of this.#queues.values()) await queue.close();
    await this.#connection.quit();
  }
}
