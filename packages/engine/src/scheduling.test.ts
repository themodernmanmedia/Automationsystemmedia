import { describe, expect, it } from 'vitest';
import { assessQueueHealth, decideSchedule, distributePostTimes } from './scheduling.js';

const inTwoHours = () => new Date(Date.now() + 2 * 3_600_000);

describe('decideSchedule', () => {
  it('delegates to Facebook, which schedules natively', () => {
    const at = inTwoHours();
    const decision = decideSchedule('FACEBOOK', at);
    expect(decision.strategy).toBe('DELEGATED');
    expect(decision.platformScheduledAt).toEqual(at);
    // Nothing for us to wake up for.
    expect(decision.fireAt).toBeNull();
  });

  it('self-times Instagram, which has no scheduling API', () => {
    const at = inTwoHours();
    const decision = decideSchedule('INSTAGRAM', at);
    expect(decision.strategy).toBe('SELF_TIMED');
    expect(decision.fireAt).toEqual(at);
    // Passing a future time to the adapter would be rejected as unsupported.
    expect(decision.platformScheduledAt).toBeNull();
    expect(decision.explanation).toMatch(/no scheduling API/i);
  });

  it('self-times TikTok for the same reason', () => {
    expect(decideSchedule('TIKTOK', inTwoHours()).strategy).toBe('SELF_TIMED');
  });

  it('publishes immediately when no time is given', () => {
    for (const platform of ['INSTAGRAM', 'TIKTOK', 'FACEBOOK'] as const) {
      expect(decideSchedule(platform, undefined).strategy).toBe('IMMEDIATE');
    }
  });

  it('treats a past timestamp as immediate rather than never firing', () => {
    expect(decideSchedule('INSTAGRAM', new Date(Date.now() - 60_000)).strategy).toBe('IMMEDIATE');
  });
});

describe('distributePostTimes', () => {
  it('spreads posts across the day and rolls into the next', () => {
    const times = distributePostTimes(6, new Date('2026-01-01T00:00:00Z'), [8, 12, 17]);
    expect(times).toHaveLength(6);
    // Three slots per day, so six posts span two days.
    const days = new Set(times.map((t) => t.getUTCDate()));
    expect(days.size).toBe(2);
  });

  it('returns times in chronological order', () => {
    const times = distributePostTimes(8, new Date('2026-01-01T00:00:00Z'));
    for (let i = 1; i < times.length; i++) {
      expect(times[i]!.getTime()).toBeGreaterThanOrEqual(times[i - 1]!.getTime());
    }
  });

  it('uses learned hours when supplied', () => {
    const times = distributePostTimes(2, new Date('2026-01-01T00:00:00Z'), [6, 22], 0);
    expect(times.map((t) => t.getUTCHours()).sort((a, b) => a - b)).toEqual([6, 22]);
  });

  it('jitters so the account does not post at exactly the same minute daily', () => {
    const runs = Array.from({ length: 12 }, () =>
      distributePostTimes(1, new Date('2026-01-01T00:00:00Z'), [12], 20)[0]!.getUTCMinutes(),
    );
    expect(new Set(runs).size).toBeGreaterThan(1);
  });
});

describe('assessQueueHealth', () => {
  const config = { minQueueHours: 24, targetQueueHours: 72, maxQueueHours: 168, maxPostsPerDay: 8 };
  const now = new Date('2026-01-01T00:00:00Z');
  const hoursOut = (h: number) => new Date(now.getTime() + h * 3_600_000);

  it('flags an empty queue as critical and asks for content', () => {
    const health = assessQueueHealth([], config, now);
    expect(health.status).toBe('CRITICAL');
    expect(health.shouldGenerate).toBe(true);
    expect(health.postsNeeded).toBeGreaterThan(0);
  });

  it('reports healthy at the target depth and asks for nothing', () => {
    const health = assessQueueHealth([hoursOut(20), hoursOut(50), hoursOut(75)], config, now);
    expect(health.status).toBe('HEALTHY');
    expect(health.shouldGenerate).toBe(false);
  });

  it('stops generating once the queue is full', () => {
    const health = assessQueueHealth([hoursOut(170)], config, now);
    expect(health.status).toBe('FULL');
    expect(health.shouldGenerate).toBe(false);
    expect(health.postsNeeded).toBe(0);
  });

  it('reports LOW between the critical and minimum thresholds', () => {
    const health = assessQueueHealth([hoursOut(18)], config, now);
    expect(health.status).toBe('LOW');
    expect(health.shouldGenerate).toBe(true);
  });

  it('ignores already-past scheduled times', () => {
    const health = assessQueueHealth([hoursOut(-10), hoursOut(-2)], config, now);
    expect(health.scheduledCount).toBe(0);
    expect(health.status).toBe('CRITICAL');
  });
});
