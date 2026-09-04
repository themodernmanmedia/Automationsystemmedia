/**
 * Queue tests against real Redis.
 *
 * These exist because of a genuine bug: every custom job id in this system used
 * ':' as a separator, which BullMQ rejects outright since it is the delimiter
 * in its own Redis keyspace. The reconciler's `publish:${id}` meant scheduled
 * publishing failed for every job — silently, because the throw happened during
 * enqueueing rather than during a publish.
 */
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { QUEUE_NAMES, QueueRegistry } from './queues.js';

const REDIS_URL = process.env['REDIS_URL'] ?? 'redis://localhost:6379';
let queues: QueueRegistry;

beforeAll(() => {
  queues = new QueueRegistry(REDIS_URL);
});
afterAll(async () => {
  await queues.drainAll();
  await queues.close();
});

describe('job ids', () => {
  it('rejects a colon, which is why every id in this system uses hyphens', async () => {
    // Guards the regression directly: if someone reintroduces ':' anywhere,
    // this documents exactly why the enqueue will fail.
    await expect(
      queues.get(QUEUE_NAMES.publishing).add('publish', {}, { jobId: 'publish:abc123' }),
    ).rejects.toThrow(/cannot contain :/i);
  });

  it('accepts the hyphenated form the reconciler actually uses', async () => {
    const job = await queues.get(QUEUE_NAMES.publishing).add(
      'publish',
      { publishingJobId: 'abc123' },
      { jobId: 'publish-abc123' },
    );
    expect(job.id).toBe('publish-abc123');
    await job.remove();
  });

  it('keeps re-arming idempotent, so a restart cannot double-publish', async () => {
    const queue = queues.get(QUEUE_NAMES.publishing);
    const first = await queue.add('publish', { publishingJobId: 'x' }, { jobId: 'publish-idempotent' });
    const second = await queue.add('publish', { publishingJobId: 'x' }, { jobId: 'publish-idempotent' });

    // Same id means BullMQ keeps one job, not two — which is what stops the
    // reconciler from queueing a duplicate post on every boot.
    expect(second.id).toBe(first.id);
    const waiting = await queue.getJobs(['waiting', 'delayed']);
    expect(waiting.filter((j) => j.id === 'publish-idempotent')).toHaveLength(1);
    await first.remove();
  });
});

describe('queue registry', () => {
  it('exposes every declared queue', () => {
    for (const name of Object.values(QUEUE_NAMES)) {
      expect(queues.get(name).name).toBe(name);
    }
  });

  it('reports counts for the automation panel', async () => {
    const stats = await queues.stats();
    expect(stats[QUEUE_NAMES.publishing]).toMatchObject({
      waiting: expect.any(Number),
      active: expect.any(Number),
      delayed: expect.any(Number),
      failed: expect.any(Number),
    });
  });

  it('drains everything pending, which is what Clear queue relies on', async () => {
    const queue = queues.get(QUEUE_NAMES.publishing);
    await queue.add('publish', { publishingJobId: 'drain-me' }, { jobId: 'publish-drain-me' });
    await queues.drainAll();
    const counts = await queue.getJobCounts('waiting', 'delayed');
    expect((counts['waiting'] ?? 0) + (counts['delayed'] ?? 0)).toBe(0);
  });
});
