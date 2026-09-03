/**
 * Tests for the publish decision gates. This is the logic that decides, with no
 * human present, whether something goes out under the brand's name — so the
 * asymmetries matter more than the happy path.
 */
import { describe, expect, it } from 'vitest';
import { decidePublish, type GateInputs } from './reviewers.js';
import { assessAssetRights, assessPostRights } from './rights.js';
import { applyFactGate, type FactCheckSummary, type CheckedClaim } from '../research/fact-checker.js';
import { optimizeCaption, runPlatformQa } from './platform-qa.js';

const passing: GateInputs = {
  safety: { verdict: 'PASS', findings: [] },
  brand: { verdict: 'PASS', score: 85, findings: [] },
  platformVerdicts: [{ platform: 'INSTAGRAM', verdict: 'PASS', issues: [] }],
  rightsPublishable: true,
  factGateAllowed: true,
  autonomousMode: true,
};

describe('decidePublish', () => {
  it('approves when every gate passes', () => {
    expect(decidePublish(passing).decision).toBe('APPROVE');
  });

  it('rejects outright on a failed safety review', () => {
    const result = decidePublish({
      ...passing,
      safety: { verdict: 'FAIL', findings: [{ category: 'defamation', severity: 'HIGH', message: 'x' }] },
    });
    expect(result.decision).toBe('REJECT');
  });

  it('lets no aggregate score outvote a high-severity safety finding', () => {
    // Perfect brand score, everything else green — still flagged.
    const result = decidePublish({
      ...passing,
      brand: { verdict: 'PASS', score: 100, findings: [] },
      safety: { verdict: 'PASS', findings: [{ category: 'misinformation', severity: 'HIGH', message: 'x' }] },
    });
    expect(result.decision).toBe('FLAG');
  });

  it('flags when the fact gate did not pass', () => {
    const result = decidePublish({
      ...passing,
      factGateAllowed: false,
      factGateReason: 'Only 2 of 9 claims verified.',
    });
    expect(result.decision).toBe('FLAG');
    expect(result.reasons[0]).toContain('2 of 9');
  });

  it('flags on unresolved copyright risk', () => {
    expect(decidePublish({ ...passing, rightsPublishable: false }).decision).toBe('FLAG');
  });

  it('flags when a target platform fails validation', () => {
    const result = decidePublish({
      ...passing,
      platformVerdicts: [{ platform: 'TIKTOK', verdict: 'FAIL', issues: [] }],
    });
    expect(result.decision).toBe('FLAG');
    expect(result.reasons[0]).toContain('TIKTOK');
  });

  it('is stricter unattended than supervised', () => {
    const warn: GateInputs = { ...passing, brand: { verdict: 'WARN', score: 70, findings: [] } };
    // Unattended, a warning goes to the exception queue.
    expect(decidePublish({ ...warn, autonomousMode: true }).decision).toBe('FLAG');
    // Supervised, a human is reviewing anyway.
    expect(decidePublish({ ...warn, autonomousMode: false }).decision).toBe('APPROVE');
  });
});

describe('applyFactGate', () => {
  const claim = (overrides: Partial<CheckedClaim>): CheckedClaim => ({
    id: 'c1',
    text: 'A claim',
    verification: 'VERIFIED',
    confidence: 0.9,
    corroborationCount: 2,
    notes: '',
    publishable: true,
    ...overrides,
  });

  function summary(claims: CheckedClaim[], overrides: Partial<FactCheckSummary> = {}): FactCheckSummary {
    return {
      claims,
      verifiedCount: claims.filter((c) => c.verification === 'VERIFIED').length,
      contradictedCount: claims.filter((c) => c.verification === 'CONTRADICTED').length,
      requiresHumanReview: false,
      ...overrides,
    };
  }

  it('permits only verified claims in autonomous mode', () => {
    const result = applyFactGate(
      summary([
        claim({ id: 'a' }),
        claim({ id: 'b', verification: 'PARTIALLY_VERIFIED', publishable: false }),
      ]),
      true,
    );
    expect(result.allowed).toBe(true);
    expect(result.usableClaims.map((c) => c.id)).toEqual(['a']);
  });

  it('blocks entirely when nothing could be verified', () => {
    const result = applyFactGate(
      summary([claim({ verification: 'UNVERIFIED', publishable: false })]),
      true,
    );
    expect(result.allowed).toBe(false);
    expect(result.reason).toMatch(/nothing safe to publish/);
  });

  it('blocks when the checker asked for human review', () => {
    const result = applyFactGate(
      summary([claim({})], { requiresHumanReview: true, reviewReason: 'Contradicted claim' }),
      true,
    );
    expect(result.allowed).toBe(false);
  });

  it('passes partially verified claims through when a human is reviewing', () => {
    const result = applyFactGate(
      summary([claim({ verification: 'PARTIALLY_VERIFIED', publishable: false })]),
      false,
    );
    expect(result.allowed).toBe(true);
    expect(result.usableClaims).toHaveLength(1);
  });

  it('treats a verified label with low confidence as not publishable', () => {
    // The checker's own signals disagreeing is a warning, not a green light.
    const result = applyFactGate(
      summary([claim({ verification: 'VERIFIED', confidence: 0.4, publishable: false })]),
      true,
    );
    expect(result.usableClaims).toHaveLength(0);
  });
});

describe('assessAssetRights', () => {
  it('clears generated and original assets', () => {
    expect(assessAssetRights({ assetSource: 'GENERATED' }).publishable).toBe(true);
    expect(assessAssetRights({ assetSource: 'ORIGINAL' }).publishable).toBe(true);
  });

  it('blocks an asset of unknown provenance', () => {
    const result = assessAssetRights({ assetSource: 'STOCK_LICENSED', sourceUrl: 'https://example.com/x.jpg' });
    expect(result.publishable).toBe(false);
    expect(result.risk).toBe('HIGH');
  });

  it('blocks a non-commercial license', () => {
    const result = assessAssetRights({ assetSource: 'STOCK_LICENSED', license: 'CC BY-NC 4.0' });
    expect(result.risk).toBe('HIGH');
    expect(result.reasons[0]).toMatch(/restricts commercial/);
  });

  it('clears a permissive license', () => {
    expect(assessAssetRights({ assetSource: 'STOCK_LICENSED', license: 'CC0' }).publishable).toBe(true);
  });

  it('blocks when attribution is required but missing', () => {
    const result = assessAssetRights({
      assetSource: 'STOCK_LICENSED',
      license: 'Unsplash',
      attributionRequired: true,
    });
    expect(result.publishable).toBe(false);
    expect(result.requiredActions[0]).toMatch(/[Aa]ttribution/);
  });

  it('does not treat public availability as a license', () => {
    const result = assessAssetRights({ assetSource: 'PUBLIC_DOMAIN' });
    expect(result.publishable).toBe(false);
  });

  it('blocks a whole post if any single asset is blocked', () => {
    const result = assessPostRights([
      { assetSource: 'GENERATED' },
      { assetSource: 'STOCK_LICENSED', license: 'editorial only' },
    ]);
    expect(result.publishable).toBe(false);
    expect(result.risk).toBe('HIGH');
    expect(result.blocking[0]!.index).toBe(1);
  });
});

describe('optimizeCaption', () => {
  it('adapts to each platform rather than using one lowest common denominator', () => {
    const long = 'Sentence. '.repeat(400); // ~4000 chars
    const ig = optimizeCaption(long, ['modernman'], 'INSTAGRAM');
    const fb = optimizeCaption(long, ['modernman'], 'FACEBOOK');
    expect(ig.characterCount).toBeLessThanOrEqual(2200);
    // Facebook's limit is far higher, so it keeps the full text.
    expect(fb.characterCount).toBeGreaterThan(ig.characterCount);
    expect(ig.withinLimit && fb.withinLimit).toBe(true);
  });

  it('caps hashtags at the platform maximum', () => {
    const tags = Array.from({ length: 50 }, (_, i) => `tag${i}`);
    expect(optimizeCaption('Short caption', tags, 'INSTAGRAM').hashtags.length).toBeLessThanOrEqual(30);
  });

  it('truncates at a sentence boundary, never mid-word', () => {
    const text = `${'This is a full sentence. '.repeat(100)}`;
    const result = optimizeCaption(text, [], 'INSTAGRAM');
    expect(result.text).toMatch(/(\.|…)(\n|$)/);
  });

  it('prefixes hashtags that arrive without one', () => {
    expect(optimizeCaption('Hi', ['money', '#business'], 'INSTAGRAM').hashtags).toEqual(['#money', '#business']);
  });
});

describe('runPlatformQa', () => {
  it('fails a Reel that exceeds the Instagram API duration cap', () => {
    const [result] = runPlatformQa([
      {
        platform: 'INSTAGRAM',
        input: {
          kind: 'REEL',
          caption: 'test',
          media: [
            {
              url: 'https://cdn.example.com/v.mp4',
              kind: 'VIDEO',
              mimeType: 'video/mp4',
              width: 1080,
              height: 1920,
              durationSec: 120,
            },
          ],
        },
      },
    ]);
    expect(result!.verdict).toBe('FAIL');
  });

  it('passes a compliant carousel', () => {
    const media = Array.from({ length: 5 }, (_, i) => ({
      url: `https://cdn.example.com/${i}.jpg`,
      kind: 'IMAGE' as const,
      mimeType: 'image/jpeg',
      width: 1080,
      height: 1350,
      fileSizeBytes: 400_000,
    }));
    const [result] = runPlatformQa([
      { platform: 'INSTAGRAM', input: { kind: 'CAROUSEL', caption: 'Test', media } },
    ]);
    expect(result!.verdict).toBe('PASS');
  });
});
