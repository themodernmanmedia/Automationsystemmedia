/**
 * AGENT 13 — BRAND QA, and the content safety reviewer.
 *
 * These are the model-backed halves of quality control; the deterministic
 * halves live in platform-qa.ts and rights.ts. Splitting them matters: the
 * deterministic checks are the ones that must never be wrong, so they do not
 * depend on a model's judgment.
 */
import { brandQaSchema, safetyReviewSchema, type BrandQa, type SafetyReview } from '@mmos/contracts';
import { Agent, type AgentContext, type AgentResult } from '../base.js';
import { PROMPTS } from '../prompts.js';

export interface ReviewInput {
  contentPieceId: string;
  /** The rendered content as a reader would encounter it. */
  content: string;
}

export class SafetyReviewerAgent extends Agent<ReviewInput, SafetyReview> {
  readonly name = 'safety_reviewer';

  constructor(ctx: AgentContext) {
    super(ctx);
  }

  protected async execute(input: ReviewInput): Promise<AgentResult<SafetyReview>> {
    const review = await this.ctx.orchestrator.completeStructured(
      {
        system: PROMPTS.SAFETY_REVIEWER.system,
        messages: [{ role: 'user', content: PROMPTS.SAFETY_REVIEWER.user(input.content) }],
        maxTokens: 2500,
        temperature: 0.1,
      },
      safetyReviewSchema,
      'SafetyReview',
      { operation: 'safety_review', contentPieceId: input.contentPieceId },
    );
    return { output: review, itemsProcessed: 1, itemsProduced: review.findings.length };
  }
}

export class BrandQaAgent extends Agent<ReviewInput, BrandQa> {
  readonly name = 'brand_qa';

  constructor(ctx: AgentContext) {
    super(ctx);
  }

  protected async execute(input: ReviewInput): Promise<AgentResult<BrandQa>> {
    const qa = await this.ctx.orchestrator.completeStructured(
      {
        system: PROMPTS.BRAND_QA.system,
        messages: [{ role: 'user', content: PROMPTS.BRAND_QA.user(input.content) }],
        maxTokens: 2500,
        temperature: 0.2,
      },
      brandQaSchema,
      'BrandQa',
      { operation: 'brand_qa', contentPieceId: input.contentPieceId },
    );
    return { output: qa, itemsProcessed: 1, itemsProduced: qa.findings.length };
  }
}

/**
 * Combines every gate into one publish decision.
 *
 * A HIGH-severity safety finding blocks regardless of anything else — no
 * aggregate score can outvote it. That asymmetry is the point: quality is a
 * spectrum, safety is a gate.
 */
export interface GateInputs {
  safety: SafetyReview;
  brand: BrandQa;
  platformVerdicts: Array<{ platform: string; verdict: 'PASS' | 'WARN' | 'FAIL'; issues: unknown[] }>;
  rightsPublishable: boolean;
  factGateAllowed: boolean;
  factGateReason?: string;
  autonomousMode: boolean;
}

export interface PublishDecision {
  decision: 'APPROVE' | 'FLAG' | 'REJECT';
  reasons: string[];
  qualityScore: number;
}

export function decidePublish(inputs: GateInputs): PublishDecision {
  const reasons: string[] = [];

  // Hard blocks, in order of severity.
  if (inputs.safety.verdict === 'FAIL') {
    reasons.push(
      `Safety review failed: ${inputs.safety.findings.map((f) => `${f.category} (${f.severity})`).join(', ')}`,
    );
    return { decision: 'REJECT', reasons, qualityScore: 0 };
  }
  if (inputs.safety.findings.some((f) => f.severity === 'HIGH')) {
    reasons.push('A high-severity safety finding requires human review.');
    return { decision: 'FLAG', reasons, qualityScore: inputs.brand.score };
  }
  if (!inputs.factGateAllowed) {
    reasons.push(inputs.factGateReason ?? 'Fact verification did not pass.');
    return { decision: 'FLAG', reasons, qualityScore: inputs.brand.score };
  }
  if (!inputs.rightsPublishable) {
    reasons.push('One or more assets carry unresolved copyright risk.');
    return { decision: 'FLAG', reasons, qualityScore: inputs.brand.score };
  }

  const failedPlatforms = inputs.platformVerdicts.filter((p) => p.verdict === 'FAIL');
  if (failedPlatforms.length > 0) {
    reasons.push(
      `Platform validation failed for: ${failedPlatforms.map((p) => p.platform).join(', ')}`,
    );
    return { decision: 'FLAG', reasons, qualityScore: inputs.brand.score };
  }

  if (inputs.brand.verdict === 'FAIL') {
    reasons.push(`Brand QA failed with a score of ${inputs.brand.score}.`);
    return { decision: 'FLAG', reasons, qualityScore: inputs.brand.score };
  }

  // Outside autonomous mode a human reviews everything, so a WARN can proceed
  // to them. Unattended, a WARN goes to the exception queue instead.
  if (inputs.brand.verdict === 'WARN' && inputs.autonomousMode) {
    reasons.push(`Brand QA raised warnings (score ${inputs.brand.score}) and autonomous mode is on.`);
    return { decision: 'FLAG', reasons, qualityScore: inputs.brand.score };
  }

  if (inputs.safety.findings.length > 0) {
    reasons.push(`${inputs.safety.findings.length} low or medium safety note(s) recorded.`);
  }
  reasons.push('All quality gates passed.');
  return { decision: 'APPROVE', reasons, qualityScore: inputs.brand.score };
}
