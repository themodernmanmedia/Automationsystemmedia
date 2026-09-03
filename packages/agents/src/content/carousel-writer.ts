/**
 * AGENT 7 — CAROUSEL WRITER.
 */
import { carouselScriptSchema, type CarouselScript } from '@mmos/contracts';
import { Agent, type AgentContext, type AgentResult } from '../base.js';
import { PROMPTS } from '../prompts.js';

export interface CarouselWriterInput {
  topicId: string;
  contentPieceId?: string;
  hook: string;
  strategy: string;
  researchSummary: string;
  verifiedClaims: string[];
  targetSlideCount?: number;
}

export class CarouselWriterAgent extends Agent<CarouselWriterInput, CarouselScript> {
  readonly name = 'carousel_writer';

  constructor(ctx: AgentContext) {
    super(ctx);
  }

  protected async execute(input: CarouselWriterInput): Promise<AgentResult<CarouselScript>> {
    const research = [
      `Summary: ${input.researchSummary}`,
      `VERIFIED facts — these are the ONLY facts you may state:\n${input.verifiedClaims.map((c) => `  - ${c}`).join('\n')}`,
      input.targetSlideCount
        ? `Aim for roughly ${input.targetSlideCount} slides, but use what the material justifies.`
        : '',
    ]
      .filter(Boolean)
      .join('\n\n');

    const script = await this.ctx.orchestrator.completeStructured(
      {
        system: PROMPTS.CAROUSEL_WRITER.system,
        messages: [
          { role: 'user', content: PROMPTS.CAROUSEL_WRITER.user(input.hook, input.strategy, research) },
        ],
        maxTokens: 5000,
        temperature: 0.7,
      },
      carouselScriptSchema,
      'CarouselScript',
      {
        operation: 'carousel_writing',
        topicId: input.topicId,
        ...(input.contentPieceId ? { contentPieceId: input.contentPieceId } : {}),
      },
    );

    // Structural repairs the model occasionally needs. The schema enforces
    // lengths; these enforce shape, which a schema cannot express.
    const slides = [...script.slides];
    if (slides[0] && slides[0].role !== 'HOOK') slides[0] = { ...slides[0], role: 'HOOK' };
    const last = slides.length - 1;
    if (slides[last] && slides[last]!.role !== 'CTA') {
      slides[last] = { ...slides[last]!, role: 'CTA' };
    }

    return {
      output: { ...script, slides },
      itemsProcessed: 1,
      itemsProduced: slides.length,
    };
  }
}
