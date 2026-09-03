/**
 * AGENT 12 — COPYRIGHT / RIGHTS AGENT.
 *
 * Assesses whether an asset is safe to publish. The governing principle from
 * the brief: public accessibility is not a license. An image being reachable on
 * the open web says nothing about the right to republish it commercially.
 *
 * LOW risk auto-publishes. MEDIUM and HIGH go to the exception queue.
 */
export type AssetSource = 'GENERATED' | 'STOCK_LICENSED' | 'PUBLIC_DOMAIN' | 'ORIGINAL' | 'BRAND_ASSET';
export type RightsRisk = 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';

export interface AssetRightsInput {
  assetSource: AssetSource;
  sourceUrl?: string;
  license?: string;
  creator?: string;
  attributionRequired?: boolean;
  attributionText?: string;
}

export interface RightsAssessment {
  risk: RightsRisk;
  publishable: boolean;
  reasons: string[];
  requiredActions: string[];
}

/** Licenses that permit commercial use without restriction. */
const PERMISSIVE = /^(cc0|public.?domain|unsplash|pexels|pixabay|mit|apache|royalty.?free)/i;
/** Licenses that forbid or condition commercial use. */
const RESTRICTIVE = /(non.?commercial|nc\b|nd\b|no.?deriv|editorial.?only|rights.?managed)/i;

export function assessAssetRights(asset: AssetRightsInput): RightsAssessment {
  const reasons: string[] = [];
  const requiredActions: string[] = [];

  // Assets we made or own carry no third-party claim.
  if (asset.assetSource === 'ORIGINAL' || asset.assetSource === 'BRAND_ASSET') {
    return { risk: 'LOW', publishable: true, reasons: ['Original or owned brand asset.'], requiredActions: [] };
  }

  if (asset.assetSource === 'GENERATED') {
    return {
      risk: 'LOW',
      publishable: true,
      reasons: ['AI-generated asset produced by this system under the provider terms.'],
      requiredActions: [],
    };
  }

  if (asset.assetSource === 'PUBLIC_DOMAIN') {
    if (!asset.sourceUrl) {
      return {
        risk: 'MEDIUM',
        publishable: false,
        reasons: ['Claimed public domain but no source URL was recorded, so the claim cannot be checked.'],
        requiredActions: ['Record the source URL and the basis for the public-domain claim.'],
      };
    }
    return { risk: 'LOW', publishable: true, reasons: ['Public domain with a recorded source.'], requiredActions: [] };
  }

  if (asset.assetSource === 'STOCK_LICENSED') {
    if (!asset.license) {
      return {
        risk: 'HIGH',
        publishable: false,
        reasons: ['Marked as licensed stock but no license was recorded.'],
        requiredActions: ['Record the specific license before this asset can be published.'],
      };
    }
    if (RESTRICTIVE.test(asset.license)) {
      return {
        risk: 'HIGH',
        publishable: false,
        reasons: [`License "${asset.license}" restricts commercial or derivative use.`],
        requiredActions: ['Replace this asset, or obtain a commercial license.'],
      };
    }
    if (PERMISSIVE.test(asset.license)) {
      reasons.push(`License "${asset.license}" permits commercial use.`);
      if (asset.attributionRequired && !asset.attributionText) {
        requiredActions.push('Attribution is required but no attribution text was supplied.');
        return { risk: 'MEDIUM', publishable: false, reasons, requiredActions };
      }
      return { risk: 'LOW', publishable: true, reasons, requiredActions };
    }
    return {
      risk: 'MEDIUM',
      publishable: false,
      reasons: [`License "${asset.license}" is not recognized, so commercial use cannot be confirmed.`],
      requiredActions: ['Have a human confirm this license permits commercial use.'],
    };
  }

  return {
    risk: 'UNKNOWN',
    publishable: false,
    reasons: ['Asset provenance is unknown. Public availability is not a license.'],
    requiredActions: ['Record the source and license, or replace with a generated or licensed asset.'],
  };
}

/** A post ships only if every asset in it ships. */
export function assessPostRights(assets: AssetRightsInput[]): {
  risk: RightsRisk;
  publishable: boolean;
  blocking: Array<{ index: number; assessment: RightsAssessment }>;
} {
  const assessments = assets.map(assessAssetRights);
  const blocking = assessments
    .map((assessment, index) => ({ index, assessment }))
    .filter((a) => !a.assessment.publishable);

  const order: RightsRisk[] = ['LOW', 'MEDIUM', 'UNKNOWN', 'HIGH'];
  const risk = assessments.reduce<RightsRisk>(
    (worst, a) => (order.indexOf(a.risk) > order.indexOf(worst) ? a.risk : worst),
    'LOW',
  );

  return { risk, publishable: blocking.length === 0, blocking };
}
