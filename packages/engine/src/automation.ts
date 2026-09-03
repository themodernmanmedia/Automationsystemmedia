/**
 * Automation state and the kill switch.
 *
 * The brief's requirement is blunt: the system must never make itself
 * impossible to stop. So the stop path is the simplest code in the repo — a
 * boolean read from one row, checked at job start AND again immediately before
 * every publish. No caching, no cleverness, nothing that can be subtly wrong.
 *
 * The second check matters: a job that passed the first check may have been
 * queued for minutes, and "stop publishing" must mean the post in flight does
 * not go out.
 */
import { prisma } from '@mmos/db';
import { ForbiddenError, type Logger } from '@mmos/core';

export interface AutomationSnapshot {
  autonomousMode: boolean;
  killSwitch: boolean;
  publishingPaused: boolean;
  agentFlags: Record<string, boolean>;
  minQueueHours: number;
  targetQueueHours: number;
  maxQueueHours: number;
  maxPostsPerDay: number;
  pausedBy: string | null;
  pausedAt: Date | null;
  lastTrendScanAt: Date | null;
  lastGenerationAt: Date | null;
  lastAnalyticsAt: Date | null;
  lastLearningAt: Date | null;
}

const DEFAULT_AGENT_FLAGS: Record<string, boolean> = {
  trendHunter: true,
  topicScorer: true,
  researcher: true,
  factChecker: true,
  strategist: true,
  hookEngine: true,
  carouselWriter: true,
  carouselDesigner: true,
  reelWriter: true,
  reelProducer: true,
  mediaSourcing: true,
  qualityControl: true,
  publisher: true,
  analytics: true,
  learningEngine: true,
};

export class AutomationService {
  constructor(private readonly logger: Logger) {}

  async get(organizationId: string): Promise<AutomationSnapshot> {
    const row = await prisma.automationState.upsert({
      where: { organizationId },
      create: { organizationId, agentFlags: DEFAULT_AGENT_FLAGS },
      update: {},
    });
    return {
      autonomousMode: row.autonomousMode,
      killSwitch: row.killSwitch,
      publishingPaused: row.publishingPaused,
      agentFlags: { ...DEFAULT_AGENT_FLAGS, ...(row.agentFlags as Record<string, boolean>) },
      minQueueHours: row.minQueueHours,
      targetQueueHours: row.targetQueueHours,
      maxQueueHours: row.maxQueueHours,
      maxPostsPerDay: row.maxPostsPerDay,
      pausedBy: row.pausedBy,
      pausedAt: row.pausedAt,
      lastTrendScanAt: row.lastTrendScanAt,
      lastGenerationAt: row.lastGenerationAt,
      lastAnalyticsAt: row.lastAnalyticsAt,
      lastLearningAt: row.lastLearningAt,
    };
  }

  /**
   * Called at the start of every job. Throws so a worker cannot accidentally
   * continue past a stop by ignoring a returned boolean.
   */
  async assertMayRun(organizationId: string, agentKey?: string): Promise<AutomationSnapshot> {
    const state = await this.get(organizationId);
    if (state.killSwitch) {
      throw new ForbiddenError('Kill switch is engaged. All automation is halted.');
    }
    if (agentKey && state.agentFlags[agentKey] === false) {
      throw new ForbiddenError(`Agent "${agentKey}" is disabled.`);
    }
    return state;
  }

  /**
   * The final check, immediately before a publish call. Deliberately separate
   * from assertMayRun: a job may have been queued for a long time, and pausing
   * publishing must stop work already in flight.
   */
  async assertMayPublish(organizationId: string): Promise<void> {
    const state = await this.get(organizationId);
    if (state.killSwitch) throw new ForbiddenError('Kill switch is engaged. Publishing is halted.');
    if (state.publishingPaused) throw new ForbiddenError('Publishing is paused.');
  }

  async setKillSwitch(organizationId: string, engaged: boolean, actor: string): Promise<void> {
    await prisma.automationState.upsert({
      where: { organizationId },
      create: {
        organizationId,
        agentFlags: DEFAULT_AGENT_FLAGS,
        killSwitch: engaged,
        pausedBy: engaged ? actor : null,
        pausedAt: engaged ? new Date() : null,
      },
      update: {
        killSwitch: engaged,
        pausedBy: engaged ? actor : null,
        pausedAt: engaged ? new Date() : null,
      },
    });
    await this.#audit(organizationId, engaged ? 'kill_switch_engaged' : 'kill_switch_released', actor);
    this.logger.warn({ organizationId, engaged, actor }, 'kill switch changed');
  }

  async setPublishingPaused(organizationId: string, paused: boolean, actor: string): Promise<void> {
    await prisma.automationState.upsert({
      where: { organizationId },
      create: { organizationId, agentFlags: DEFAULT_AGENT_FLAGS, publishingPaused: paused },
      update: { publishingPaused: paused },
    });
    await this.#audit(organizationId, paused ? 'publishing_paused' : 'publishing_resumed', actor);
  }

  async setAutonomousMode(organizationId: string, enabled: boolean, actor: string): Promise<void> {
    await prisma.automationState.upsert({
      where: { organizationId },
      create: { organizationId, agentFlags: DEFAULT_AGENT_FLAGS, autonomousMode: enabled },
      update: { autonomousMode: enabled },
    });
    await this.#audit(organizationId, enabled ? 'autonomous_mode_on' : 'autonomous_mode_off', actor);
  }

  async setAgentEnabled(
    organizationId: string,
    agentKey: string,
    enabled: boolean,
    actor: string,
  ): Promise<void> {
    const state = await this.get(organizationId);
    await prisma.automationState.update({
      where: { organizationId },
      data: { agentFlags: { ...state.agentFlags, [agentKey]: enabled } },
    });
    await this.#audit(organizationId, enabled ? 'agent_enabled' : 'agent_disabled', actor, agentKey);
  }

  async #audit(organizationId: string, action: string, actor: string, subjectId?: string): Promise<void> {
    await prisma.auditLog.create({
      data: {
        organizationId,
        actorType: 'user',
        actorId: actor,
        action,
        ...(subjectId ? { subjectType: 'agent', subjectId } : {}),
      },
    });
  }
}
