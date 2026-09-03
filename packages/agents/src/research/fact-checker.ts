/**
 * AGENT 4 — FACT CHECKER.
 *
 * The gate that makes autonomous publishing defensible. In autonomous mode only
 * VERIFIED claims may reach a published asset; anything else is rewritten,
 * dropped, or sends the whole piece to the exception queue.
 *
 * Enforcement lives here in code rather than in a prompt, because a prompt
 * instruction is a request and this needs to be a rule.
 */
import { factCheckSchema } from '@mmos/contracts';
import { Agent, type AgentContext, type AgentResult } from '../base.js';
import { PROMPTS } from '../prompts.js';
import type { ResearchedSource } from './researcher.js';

export type Verification = 'VERIFIED' | 'PARTIALLY_VERIFIED' | 'UNVERIFIED' | 'CONTRADICTED';

export interface ClaimToCheck {
  id: string;
  text: string;
  claimType: string;
  supportingExcerpt: string;
}

export interface CheckedClaim {
  id: string;
  text: string;
  verification: Verification;
  confidence: number;
  corroborationCount: number;
  notes: string;
  suggestedRewrite?: string;
  /** True when this claim may be used verbatim in auto-published content. */
  publishable: boolean;
}

export interface FactCheckSummary {
  claims: CheckedClaim[];
  verifiedCount: number;
  contradictedCount: number;
  /** True when the piece must not auto-publish and needs a human. */
  requiresHumanReview: boolean;
  reviewReason?: string;
}

export class FactCheckerAgent extends Agent<
  { topicId: string; claims: ClaimToCheck[]; sources: ResearchedSource[] },
  FactCheckSummary
> {
  readonly name = 'fact_checker';

  constructor(ctx: AgentContext) {
    super(ctx);
  }

  protected async execute(input: {
    topicId: string;
    claims: ClaimToCheck[];
    sources: ResearchedSource[];
  }): Promise<AgentResult<FactCheckSummary>> {
    if (input.claims.length === 0) {
      return {
        output: { claims: [], verifiedCount: 0, contradictedCount: 0, requiresHumanReview: false },
        itemsProcessed: 0,
        itemsProduced: 0,
      };
    }

    const renderedSources = input.sources
      .map(
        (s, i) =>
          `[SOURCE ${i + 1}] ${s.title} (${s.publisher ?? 'unknown'}, credibility ${s.credibility})\nURL: ${s.url}\n${(s.fullText ?? s.excerpt).slice(0, 5000)}`,
      )
      .join('\n\n---\n\n');

    const renderedClaims = input.claims.map((c, i) => `[${i + 1}] (${c.claimType}) ${c.text}`).join('\n');

    const result = await this.ctx.orchestrator.completeStructured(
      {
        system: PROMPTS.FACT_CHECKER.system,
        messages: [{ role: 'user', content: PROMPTS.FACT_CHECKER.user(renderedClaims, renderedSources) }],
        maxTokens: 6000,
        temperature: 0.1, // verification must be as deterministic as we can make it
      },
      factCheckSchema,
      'FactCheck',
      { operation: 'fact_check', topicId: input.topicId },
    );

    // Match results back by claim text; an unmatched claim is treated as
    // UNVERIFIED rather than assumed fine. Silence is not verification.
    const byText = new Map(result.results.map((r) => [normalize(r.claimText), r]));

    const claims: CheckedClaim[] = input.claims.map((claim) => {
      const found = byText.get(normalize(claim.text));
      if (!found) {
        return {
          id: claim.id,
          text: claim.text,
          verification: 'UNVERIFIED' as const,
          confidence: 0,
          corroborationCount: 0,
          notes: 'The fact checker returned no verdict for this claim; treated as unverified.',
          publishable: false,
        };
      }
      return {
        id: claim.id,
        text: claim.text,
        verification: found.verification,
        confidence: found.confidence,
        corroborationCount: found.corroborationCount,
        notes: found.notes,
        ...(found.suggestedRewrite ? { suggestedRewrite: found.suggestedRewrite } : {}),
        // Both conditions required. A VERIFIED label with low confidence is not
        // a green light — the two disagreeing is itself a warning sign.
        publishable: found.verification === 'VERIFIED' && found.confidence >= 0.7,
      };
    });

    const verifiedCount = claims.filter((c) => c.verification === 'VERIFIED').length;
    const contradictedCount = claims.filter((c) => c.verification === 'CONTRADICTED').length;

    // Any contradiction stops the piece outright. A majority of unverifiable
    // claims means the research was too thin to build on.
    let requiresHumanReview = false;
    let reviewReason: string | undefined;
    if (contradictedCount > 0) {
      requiresHumanReview = true;
      reviewReason = `${contradictedCount} claim(s) are contradicted by the sources.`;
    } else if (claims.length > 0 && verifiedCount / claims.length < 0.5) {
      requiresHumanReview = true;
      reviewReason = `Only ${verifiedCount} of ${claims.length} claims could be verified.`;
    }

    return {
      output: {
        claims,
        verifiedCount,
        contradictedCount,
        requiresHumanReview,
        ...(reviewReason ? { reviewReason } : {}),
      },
      itemsProcessed: input.claims.length,
      itemsProduced: verifiedCount,
    };
  }
}

/**
 * The publish gate itself. Called by the QA pipeline before anything ships.
 * Returns the claims that may be used, and whether the piece can proceed at all.
 */
export function applyFactGate(
  summary: FactCheckSummary,
  autonomousMode: boolean,
): { allowed: boolean; usableClaims: CheckedClaim[]; reason?: string } {
  if (summary.requiresHumanReview) {
    return {
      allowed: false,
      usableClaims: summary.claims.filter((c) => c.publishable),
      reason: summary.reviewReason ?? 'Fact check requires human review.',
    };
  }

  const usableClaims = summary.claims.filter((c) => c.publishable);

  // Outside autonomous mode a human is reviewing anyway, so partially verified
  // material can proceed to them. Unattended, only verified claims survive.
  if (!autonomousMode) {
    return { allowed: true, usableClaims: summary.claims.filter((c) => c.verification !== 'CONTRADICTED') };
  }

  if (summary.claims.length > 0 && usableClaims.length === 0) {
    return {
      allowed: false,
      usableClaims: [],
      reason: 'No claims passed verification, so there is nothing safe to publish.',
    };
  }

  return { allowed: true, usableClaims };
}

function normalize(text: string): string {
  return text.toLowerCase().replace(/\s+/g, ' ').trim();
}
