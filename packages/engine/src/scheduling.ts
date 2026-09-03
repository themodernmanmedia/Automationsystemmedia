/**
 * Scheduling strategy selection.
 *
 * The single most consequential design decision in this system. Instagram and
 * TikTok accept no future timestamp, so "scheduled" means we hold the job and
 * fire it ourselves. Facebook accepts one, so we hand it over and let Facebook
 * do the waiting — fewer moving parts, and it survives our worker being down.
 *
 * Choosing per platform from the capability registry, rather than picking one
 * uniform approach, is what makes this correct on all three.
 */
import { getCapabilities, type PlatformName } from '@mmos/platforms';

export type ScheduleStrategy = 'DELEGATED' | 'SELF_TIMED' | 'IMMEDIATE';

export interface ScheduleDecision {
  strategy: ScheduleStrategy;
  /** Time we wake ourselves. Null when the platform is doing the waiting. */
  fireAt: Date | null;
  /** Timestamp handed to the platform. Null when we hold the job. */
  platformScheduledAt: Date | null;
  explanation: string;
}

export function decideSchedule(platform: PlatformName, scheduledAt: Date | undefined): ScheduleDecision {
  const caps = getCapabilities(platform);

  if (!scheduledAt || scheduledAt.getTime() <= Date.now()) {
    return {
      strategy: 'IMMEDIATE',
      fireAt: new Date(),
      platformScheduledAt: null,
      explanation: 'No future time requested; publishing immediately.',
    };
  }

  if (caps?.canSchedule && caps.scheduleStrategy === 'DELEGATED') {
    return {
      strategy: 'DELEGATED',
      fireAt: null,
      platformScheduledAt: scheduledAt,
      explanation: `${caps.displayName} supports native scheduling, so the timestamp is handed to the platform and it publishes without us.`,
    };
  }

  return {
    strategy: 'SELF_TIMED',
    fireAt: scheduledAt,
    platformScheduledAt: null,
    explanation: `${caps?.displayName ?? platform} has no scheduling API, so this system holds the job and publishes at the target time.`,
  };
}

/**
 * Spreads posts across a day.
 *
 * Uses learned best hours when there is enough evidence, and otherwise falls
 * back to sensible defaults — the brief warns against fixed times forever, but
 * guessing from three posts is not better than a default. Slots are jittered so
 * the account does not post at exactly :00 every day, which looks automated.
 */
export function distributePostTimes(
  count: number,
  date: Date,
  preferredHours: number[] = [],
  jitterMinutes = 20,
): Date[] {
  const hours = preferredHours.length >= 2 ? preferredHours : [8, 12, 17, 20];
  const times: Date[] = [];

  for (let i = 0; i < count; i++) {
    const hour = hours[i % hours.length] ?? 12;
    // Additional days once the day's slots are used up.
    const dayOffset = Math.floor(i / hours.length);
    const slot = new Date(date);
    slot.setUTCDate(slot.getUTCDate() + dayOffset);
    slot.setUTCHours(hour, 0, 0, 0);

    const jitter = Math.floor((Math.random() - 0.5) * 2 * jitterMinutes);
    slot.setUTCMinutes(slot.getUTCMinutes() + jitter);
    times.push(slot);
  }

  return times.sort((a, b) => a.getTime() - b.getTime());
}

/**
 * Queue health against the configured backlog window.
 *
 * The autonomous loop generates when the queue falls below the minimum and
 * stops when it exceeds the maximum, so the system maintains a healthy backlog
 * without producing content indefinitely.
 */
export interface QueueHealth {
  scheduledCount: number;
  hoursOfContent: number;
  status: 'CRITICAL' | 'LOW' | 'HEALTHY' | 'FULL';
  shouldGenerate: boolean;
  postsNeeded: number;
}

export function assessQueueHealth(
  scheduledTimes: Date[],
  config: { minQueueHours: number; targetQueueHours: number; maxQueueHours: number; maxPostsPerDay: number },
  now: Date = new Date(),
): QueueHealth {
  const future = scheduledTimes.filter((t) => t.getTime() > now.getTime()).sort((a, b) => a.getTime() - b.getTime());
  const last = future[future.length - 1];
  const hoursOfContent = last ? (last.getTime() - now.getTime()) / 3_600_000 : 0;

  const status =
    hoursOfContent < config.minQueueHours / 2
      ? ('CRITICAL' as const)
      : hoursOfContent < config.minQueueHours
        ? ('LOW' as const)
        : hoursOfContent >= config.maxQueueHours
          ? ('FULL' as const)
          : ('HEALTHY' as const);

  const shouldGenerate = hoursOfContent < config.targetQueueHours && status !== 'FULL';
  const hoursShort = Math.max(0, config.targetQueueHours - hoursOfContent);
  const postsNeeded = shouldGenerate
    ? Math.ceil((hoursShort / 24) * config.maxPostsPerDay)
    : 0;

  return {
    scheduledCount: future.length,
    hoursOfContent: Number(hoursOfContent.toFixed(1)),
    status,
    shouldGenerate,
    postsNeeded,
  };
}
