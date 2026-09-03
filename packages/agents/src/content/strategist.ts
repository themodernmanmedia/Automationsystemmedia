/**
 * AGENT 5 — CONTENT STRATEGIST.
 *
 * Decides format, angle, structure, and target platforms. It receives the
 * platform capability registry so it cannot select a format a target platform
 * genuinely cannot publish.
 */
import { contentStrategySchema, type ContentStrategy } from '@mmos/contracts';
import { getCapabilities, type PlatformName } from '@mmos/platforms';
import { Agent, type AgentContext, type AgentResult } from '../base.js';
import { PROMPTS } from '../prompts.js';

export interface StrategyInput {
  topicId: string;
  title: string;
  researchSummary: string;
  keyFindings: string[];
  verifiedClaims: string[];
  availablePlatforms: PlatformName[];
  /** Format hints from the learning engine, e.g. { CAROUSEL: 1.3 }. */
  formatPerformance?: Record<string, number>;
}

export class StrategistAgent extends Agent<StrategyInput, ContentStrategy> {
  readonly name = 'content_strategist';

  constructor(ctx: AgentContext) {
    super(ctx);
  }

  protected async execute(input: StrategyInput): Promise<AgentResult<ContentStrategy>> {
    const performanceNote = input.formatPerformance
      ? `\n\nMeasured performance by format for this brand (1.0 = average):\n${Object.entries(
          input.formatPerformance,
        )
          .map(([f, lift]) => `  ${f}: ${lift.toFixed(2)}x`)
          .join('\n')}\nTreat this as evidence, not an instruction: pick the format the material justifies.`
      : '';

    const research = [
      `Topic: ${input.title}`,
      `Summary: ${input.researchSummary}`,
      `Key findings:\n${input.keyFindings.map((f) => `  - ${f}`).join('\n')}`,
      `Verified claims available to use:\n${input.verifiedClaims.map((c) => `  - ${c}`).join('\n')}`,
      `Connected platforms: ${input.availablePlatforms.join(', ')}`,
      performanceNote,
    ].join('\n\n');

    const strategy = await this.ctx.orchestrator.completeStructured(
      {
        system: PROMPTS.STRATEGIST.system,
        messages: [{ role: 'user', content: PROMPTS.STRATEGIST.user(research) }],
        maxTokens: 2000,
        temperature: 0.6,
      },
      contentStrategySchema,
      'ContentStrategy',
      { operation: 'content_strategy', topicId: input.topicId },
    );

    // Drop any target the capability registry says cannot carry this format.
    // Cheaper to correct here than to fail platform QA later.
    const viable = strategy.targetPlatforms.filter((p) => {
      if (!input.availablePlatforms.includes(p)) return false;
      const caps = getCapabilities(p);
      if (!caps) return false;
      switch (strategy.format) {
        case 'CAROUSEL':
          return caps.canPostCarousel;
        case 'REEL':
          return caps.canPostVideo;
        case 'SINGLE_IMAGE':
          return caps.canPostImage;
        case 'STORY':
          return caps.canPostStory;
        default:
          return true;
      }
    });

    if (viable.length === 0) {
      this.ctx.logger.warn(
        { format: strategy.format, requested: strategy.targetPlatforms },
        'no connected platform supports the chosen format; falling back to the connected set',
      );
    }

    return {
      output: { ...strategy, targetPlatforms: viable.length > 0 ? viable : input.availablePlatforms },
      itemsProcessed: 1,
      itemsProduced: 1,
    };
  }
}
