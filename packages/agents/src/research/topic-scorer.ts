/**
 * AGENT 2 — TOPIC SCORER.
 *
 * The model judges each dimension; the composite is computed in code from
 * configurable weights. That split is deliberate: the weights are tuned by the
 * learning engine, and arithmetic done in code is reproducible and free.
 */
import { topicScoreSchema } from '@mmos/contracts';
import { DEFAULT_SCORING_WEIGHTS } from '@mmos/core';
import { Agent, type AgentContext, type AgentResult } from '../base.js';
import { PROMPTS } from '../prompts.js';
import {
  computeCompositeScore,
  timelinessScore,
  type DimensionScores,
  type ScoringWeights,
} from './scoring.js';

export interface TopicToScore {
  id: string;
  title: string;
  summary: string;
  category: string;
  isBreakingNews: boolean;
  discoveredAt: Date;
}

export interface ScoredTopic {
  id: string;
  dimensionScores: DimensionScores;
  compositeScore: number;
  reasoning: string;
}

export class TopicScorerAgent extends Agent<
  { topics: TopicToScore[]; weights?: ScoringWeights },
  ScoredTopic[]
> {
  readonly name = 'topic_scorer';

  constructor(ctx: AgentContext) {
    super(ctx);
  }

  protected async execute(input: {
    topics: TopicToScore[];
    weights?: ScoringWeights;
  }): Promise<AgentResult<ScoredTopic[]>> {
    const weights = input.weights ?? DEFAULT_SCORING_WEIGHTS;
    const scored: ScoredTopic[] = [];

    for (const topic of input.topics) {
      try {
        const result = await this.ctx.orchestrator.completeStructured(
          {
            system: PROMPTS.TOPIC_SCORER.system,
            messages: [
              {
                role: 'user',
                content: PROMPTS.TOPIC_SCORER.user(
                  `Title: ${topic.title}\nCategory: ${topic.category}\nSummary: ${topic.summary}\nBreaking news: ${topic.isBreakingNews}`,
                ),
              },
            ],
            maxTokens: 1500,
            temperature: 0.3, // scoring should be stable, not creative
          },
          topicScoreSchema,
          'TopicScore',
          { operation: 'topic_scoring', topicId: topic.id },
        );

        // Override the model's TIMELINESS with a computed decay. The model
        // cannot know how long the topic has been sitting in the queue.
        const dimensionScores: DimensionScores = {
          ...result.scores,
          TIMELINESS: timelinessScore(topic.discoveredAt, topic.isBreakingNews),
        };

        scored.push({
          id: topic.id,
          dimensionScores,
          compositeScore: computeCompositeScore(dimensionScores, weights).composite,
          reasoning: result.reasoning,
        });
      } catch (err) {
        // One unscoreable topic must not abandon the batch.
        this.ctx.logger.warn({ err, topicId: topic.id }, 'failed to score topic; skipping');
      }
    }

    scored.sort((a, b) => b.compositeScore - a.compositeScore);
    return { output: scored, itemsProcessed: input.topics.length, itemsProduced: scored.length };
  }
}
