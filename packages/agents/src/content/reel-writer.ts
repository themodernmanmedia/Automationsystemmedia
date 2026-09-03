/**
 * AGENT 9 — REEL WRITER.
 */
import { reelScriptSchema, type ReelScript } from '@mmos/contracts';
import { getCapabilities } from '@mmos/platforms';
import { Agent, type AgentContext, type AgentResult } from '../base.js';
import { PROMPTS } from '../prompts.js';

export interface ReelWriterInput {
  topicId: string;
  contentPieceId?: string;
  hook: string;
  strategy: string;
  researchSummary: string;
  verifiedClaims: string[];
  targetDurationSec?: number;
}

export interface ReelScriptResult extends ReelScript {
  totalDurationSec: number;
  voiceoverText: string;
}

export class ReelWriterAgent extends Agent<ReelWriterInput, ReelScriptResult> {
  readonly name = 'reel_writer';

  constructor(ctx: AgentContext) {
    super(ctx);
  }

  protected async execute(input: ReelWriterInput): Promise<AgentResult<ReelScriptResult>> {
    // Instagram caps API-published Reels at 90s, so that is the real ceiling
    // regardless of what the strategy asked for.
    const maxDuration = getCapabilities('INSTAGRAM')?.video.maxDurationSec ?? 90;
    const target = Math.min(input.targetDurationSec ?? 45, maxDuration);

    const research = [
      `Summary: ${input.researchSummary}`,
      `VERIFIED facts — the ONLY facts you may state:\n${input.verifiedClaims.map((c) => `  - ${c}`).join('\n')}`,
      `Target runtime: about ${target} seconds. Hard maximum ${maxDuration} seconds (the Instagram API limit).`,
    ].join('\n\n');

    const script = await this.ctx.orchestrator.completeStructured(
      {
        system: PROMPTS.REEL_WRITER.system,
        messages: [{ role: 'user', content: PROMPTS.REEL_WRITER.user(input.hook, input.strategy, research) }],
        maxTokens: 5000,
        temperature: 0.75,
      },
      reelScriptSchema,
      'ReelScript',
      {
        operation: 'reel_writing',
        topicId: input.topicId,
        ...(input.contentPieceId ? { contentPieceId: input.contentPieceId } : {}),
      },
    );

    let beats = [...script.beats];
    if (beats[0] && beats[0].beat !== 'HOOK') beats[0] = { ...beats[0], beat: 'HOOK' };

    // Models routinely overrun the requested runtime. Scale the beats down
    // proportionally rather than truncating, which would cut the payoff.
    let total = beats.reduce((sum, b) => sum + b.durationSec, 0);
    if (total > maxDuration) {
      const factor = maxDuration / total;
      beats = beats.map((b) => ({ ...b, durationSec: Number((b.durationSec * factor).toFixed(2)) }));
      total = beats.reduce((sum, b) => sum + b.durationSec, 0);
      this.ctx.logger.info(
        { originalSec: Number((total / factor).toFixed(1)), scaledSec: Number(total.toFixed(1)) },
        'scaled reel beats to fit the platform duration limit',
      );
    }

    return {
      output: {
        ...script,
        beats,
        totalDurationSec: Number(total.toFixed(2)),
        voiceoverText: beats.map((b) => b.narration).join(' '),
      },
      itemsProcessed: 1,
      itemsProduced: beats.length,
    };
  }
}
