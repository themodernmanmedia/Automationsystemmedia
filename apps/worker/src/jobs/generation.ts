/**
 * Content generation.
 *
 * Takes a researched topic through strategy, hook selection, writing, design,
 * rendering, and every quality gate, ending either APPROVED and scheduled or
 * FLAGGED for a human. The gates are applied here in code rather than trusted
 * to prompts, which is what makes unattended operation defensible.
 */
import { type Logger } from '@mmos/core';
import { prisma } from '@mmos/db';
import type { AiOrchestrator, ImageProvider, StockImageProvider, StorageProvider } from '@mmos/ai';
import {
  BrandQaAgent,
  MediaSourcingAgent,
  collectAttributions,
  CarouselWriterAgent,
  HookEngineAgent,
  ReelWriterAgent,
  SafetyReviewerAgent,
  StrategistAgent,
  applyFactGate,
  assessPostRights,
  computeViralPotential,
  contentHash,
  decidePublish,
  designCarousel,
  isDuplicate,
  optimizeCaption,
  runPlatformQa,
  similarity,
  SIMILARITY_THRESHOLDS,
  type AgentContext,
  type CheckedClaim,
} from '@mmos/agents';
import { CarouselRenderer } from '@mmos/media';
import type { PlatformName, CreatePostInput } from '@mmos/platforms';
import type { AutomationService } from '@mmos/engine';
import { DbRunSink } from './pipeline.js';
import { assignToExperiment } from './experiments.js';

export interface GenerationDeps {
  organizationId: string;
  orchestrator: AiOrchestrator;
  storage: StorageProvider | null;
  automation: AutomationService;
  logger: Logger;
  chromiumPath?: string;
  /** Optional. Without either, slides render on the brand background. */
  image?: ImageProvider | null;
  stock?: StockImageProvider[];
}

export interface GenerationResult {
  contentPieceId: string;
  status: 'APPROVED' | 'FLAGGED';
  format: string;
  reasons: string[];
}

export async function generateFromTopic(
  deps: GenerationDeps,
  topicId: string,
): Promise<GenerationResult> {
  const state = await deps.automation.assertMayRun(deps.organizationId, 'strategist');
  const log = deps.logger.child({ topicId });

  const topic = await prisma.topic.findFirst({
    where: { id: topicId, organizationId: deps.organizationId },
    include: { claims: true, researchReports: { orderBy: { createdAt: 'desc' }, take: 1 } },
  });
  if (!topic) throw new Error(`Topic not found: ${topicId}`);

  const report = topic.researchReports[0];
  if (!report) throw new Error(`Topic ${topicId} has no research report; run research first.`);

  const ctx: AgentContext = {
    organizationId: deps.organizationId,
    orchestrator: deps.orchestrator,
    logger: deps.logger,
    runSink: new DbRunSink(deps.organizationId),
  };

  /* ---- the fact gate, before a single token is spent on writing ---- */

  const checked: CheckedClaim[] = topic.claims.map((c) => ({
    id: c.id,
    text: c.text,
    verification: c.verification,
    confidence: c.confidence,
    corroborationCount: c.corroborationCount,
    notes: c.verifierNotes ?? '',
    publishable: c.verification === 'VERIFIED' && c.confidence >= 0.7,
  }));

  const factGate = applyFactGate(
    {
      claims: checked,
      verifiedCount: checked.filter((c) => c.verification === 'VERIFIED').length,
      contradictedCount: checked.filter((c) => c.verification === 'CONTRADICTED').length,
      requiresHumanReview: false,
    },
    state.autonomousMode,
  );

  if (!factGate.allowed) {
    log.warn({ reason: factGate.reason }, 'generation halted before writing: fact gate');
    throw new Error(`Fact gate blocked generation: ${factGate.reason}`);
  }

  const verifiedClaims = factGate.usableClaims.map((c) => c.text);

  /* ---- strategy ---- */

  const accounts = await prisma.socialAccount.findMany({
    where: { organizationId: deps.organizationId, status: 'CONNECTED' },
  });
  const availablePlatforms = [...new Set(accounts.map((a) => a.platform as PlatformName))];
  if (availablePlatforms.length === 0) {
    throw new Error('No connected social accounts; there is nowhere to publish.');
  }

  const strategy = await new StrategistAgent(ctx).run({
    topicId,
    title: topic.title,
    researchSummary: report.summary,
    keyFindings: report.keyFindings,
    verifiedClaims,
    availablePlatforms,
  });

  /* ---- hook, deduped against what has already been used ---- */

  const previous = await prisma.contentPiece.findMany({
    where: { organizationId: deps.organizationId, createdAt: { gte: new Date(Date.now() - 60 * 86_400_000) } },
    select: { id: true, hook: true, title: true },
    take: 300,
  });

  const hookResult = await new HookEngineAgent(ctx).run({
    topicId,
    title: topic.title,
    researchSummary: report.summary,
    verifiedClaims,
    count: 20,
    previousHooks: previous.map((p) => p.hook),
  });

  /* ---- content piece ---- */

  const format = strategy.format === 'REEL' ? 'REEL' : 'CAROUSEL';
  const piece = await prisma.contentPiece.create({
    data: {
      organizationId: deps.organizationId,
      brandId: topic.brandId,
      topicId,
      format,
      status: 'WRITING',
      category: topic.category,
      title: topic.title,
      hook: hookResult.selected.text,
      hookArchetype: hookResult.selected.archetype,
      cta: strategy.cta,
      contentHash: contentHash(`${topic.title} ${hookResult.selected.text}`),
    },
  });

  // Join a running experiment, if one is open. Assignment is deterministic on
  // the piece id, so a regenerated piece stays in the same arm.
  const assignment = await assignToExperiment(deps.organizationId, piece.id, deps.logger);

  const attribution = { operation: 'generation', topicId, contentPieceId: piece.id };
  log.info(
    { contentPieceId: piece.id, format, experimentArm: assignment?.variant ?? null },
    'generating content',
  );

  const strategyText = [
    `Angle: ${strategy.angle}`,
    `Structure: ${strategy.storyStructure}`,
    `Audience: ${strategy.audience}`,
    `Tone: ${strategy.tone}`,
    `Visuals: ${strategy.visualDirection}`,
    `CTA: ${strategy.cta}`,
  ].join('\n');

  let caption = '';
  let hashtags: string[] = [];
  let renderedBody = '';
  let imageCostUsd = 0;

  if (format === 'CAROUSEL') {
    const script = await new CarouselWriterAgent(ctx).run({
      topicId,
      contentPieceId: piece.id,
      hook: hookResult.selected.text,
      strategy: strategyText,
      researchSummary: report.summary,
      verifiedClaims,
    });

    caption = script.caption;
    hashtags = script.hashtags;
    renderedBody = script.slides.map((s) => `[${s.role}] ${s.headline}\n${s.body}`).join('\n\n');

    const designed = designCarousel(script);
    const carousel = await prisma.carouselPost.create({
      data: { contentPieceId: piece.id, slideCount: designed.slides.length, aspectRatio: designed.aspectRatio },
    });

    for (const slide of designed.slides) {
      await prisma.carouselSlide.create({
        data: {
          carouselPostId: carousel.id,
          position: slide.position,
          headline: slide.headline,
          body: slide.body,
          slideRole: slide.role,
          design: slide.design as unknown as object,
        },
      });
    }

    await prisma.contentPiece.update({ where: { id: piece.id }, data: { status: 'DESIGNING' } });

    // Source imagery for slides whose design calls for it. Every asset arrives
    // with provenance, and anything that cannot be sourced falls back to the
    // brand background rather than blocking the post.
    const slideImages: Record<number, string> = {};
    const sourcedRights: Array<{ position: number; rights: Parameters<typeof assessPostRights>[0][number] }> = [];

    const canSource = Boolean(deps.image) || (deps.stock?.length ?? 0) > 0;
    if (canSource && deps.storage) {
      const sourcer = new MediaSourcingAgent({
        image: deps.image ?? null,
        stock: deps.stock ?? [],
        logger: deps.logger,
      });

      for (const slide of designed.slides) {
        if (slide.design.imagePosition === 'NONE') continue;
        const direction = slide.design.imagePrompt ?? slide.headline;

        const sourced = await sourcer.source({
          visualDirection: direction,
          keywords: topic.keywords,
          width: 1080,
          height: 1350,
        });
        if (sourced.origin === 'NONE') continue;

        // Stock is referenced by URL; generated bytes are uploaded to our own
        // storage so the renderer and the platforms can both reach it.
        let imageUrl = sourced.remoteUrl;
        if (sourced.data) {
          const stored = await deps.storage.put(
            `carousels/${piece.id}/visual-${slide.position}.png`,
            sourced.data,
            sourced.mimeType,
          );
          imageUrl = stored.publicUrl;
        }
        if (!imageUrl) continue;

        slideImages[slide.position] = imageUrl;
        sourcedRights.push({ position: slide.position, rights: sourced.rights });

        await prisma.mediaAsset.create({
          data: {
            contentPieceId: piece.id,
            kind: 'broll',
            storageKey: sourced.data ? `carousels/${piece.id}/visual-${slide.position}.png` : '',
            publicUrl: imageUrl,
            mimeType: sourced.mimeType,
            width: sourced.width ?? null,
            height: sourced.height ?? null,
            assetSource: sourced.rights.assetSource,
            sourceUrl: sourced.rights.sourceUrl ?? null,
            license: sourced.rights.license ?? null,
            creator: sourced.rights.creator ?? null,
            attributionRequired: sourced.rights.attributionRequired ?? false,
            attributionText: sourced.rights.attributionText ?? null,
            // The rights agent re-evaluates this below; recorded for the audit trail.
            rightsRisk: sourced.origin === 'GENERATED' ? 'LOW' : 'MEDIUM',
            ...(sourced.origin === 'GENERATED' ? { generationPrompt: direction } : {}),
          },
        });

        if (sourced.costUsd > 0) imageCostUsd += sourced.costUsd;
      }

      log.info({ sourced: Object.keys(slideImages).length }, 'slide imagery sourced');
    }

    // Attribution is a licence condition, so it must reach the caption rather
    // than sit unread in the database.
    const attributions = collectAttributions(sourcedRights.map((r) => r.rights));
    if (attributions.length > 0) {
      caption = `${caption}\n\n${attributions.join(' · ')}`;
    }

    // Rendering requires storage, because Meta fetches media from a public URL.
    if (deps.storage) {
      const renderer = new CarouselRenderer({
        logger: deps.logger,
        ...(deps.chromiumPath ? { executablePath: deps.chromiumPath } : {}),
      });
      const rendered = await renderer.render(designed, {
        brandName: 'The Modern Man',
        slideImages,
      });

      for (const slide of rendered) {
        const stored = await deps.storage.put(
          `carousels/${piece.id}/slide-${slide.position}.jpg`,
          slide.data,
          'image/jpeg',
        );
        await prisma.carouselSlide.updateMany({
          where: { carouselPostId: carousel.id, position: slide.position },
          data: { renderedImageUrl: stored.publicUrl },
        });
        await prisma.mediaAsset.create({
          data: {
            contentPieceId: piece.id,
            kind: 'image',
            storageKey: stored.key,
            publicUrl: stored.publicUrl,
            mimeType: 'image/jpeg',
            width: slide.width,
            height: slide.height,
            fileSizeBytes: stored.sizeBytes,
            // Rendered from our own design system, so rights are unambiguous.
            assetSource: 'ORIGINAL',
            rightsRisk: 'LOW',
          },
        });
      }
    } else {
      log.warn('storage is not configured; slides were designed but not rendered or uploaded');
    }
  } else {
    const script = await new ReelWriterAgent(ctx).run({
      topicId,
      contentPieceId: piece.id,
      hook: hookResult.selected.text,
      strategy: strategyText,
      researchSummary: report.summary,
      verifiedClaims,
    });

    caption = script.caption;
    hashtags = script.hashtags;
    renderedBody = script.beats.map((b) => `[${b.beat}] ${b.narration}`).join('\n');

    await prisma.reel.create({
      data: {
        contentPieceId: piece.id,
        durationSec: script.totalDurationSec,
        scriptBeats: script.beats as unknown as object,
        voiceoverText: script.voiceoverText,
        // Rendering needs voice and visual providers; the render worker picks
        // this up and fails visibly if they are absent.
        renderStatus: 'PENDING',
      },
    });
  }

  await prisma.contentPiece.update({
    where: { id: piece.id },
    data: { status: 'QA', scriptBody: renderedBody },
  });

  /* ---- duplicate check against recent output ---- */

  const duplicate = isDuplicate(
    `${topic.title} ${renderedBody}`,
    previous.map((p) => ({ id: p.id, text: `${p.title} ${p.hook}` })),
    SIMILARITY_THRESHOLDS.script,
  );

  /* ---- quality gates ---- */

  const fullContent = `HOOK: ${hookResult.selected.text}\n\n${renderedBody}\n\nCAPTION: ${caption}`;

  const [safety, brand] = await Promise.all([
    new SafetyReviewerAgent(ctx).run({ contentPieceId: piece.id, content: fullContent }),
    new BrandQaAgent(ctx).run({ contentPieceId: piece.id, content: fullContent }),
  ]);

  // Captions are optimized per platform, since limits genuinely differ.
  const targets: Array<{ platform: PlatformName; input: CreatePostInput }> = [];
  for (const platform of strategy.targetPlatforms) {
    const optimized = optimizeCaption(caption, hashtags, platform);
    await prisma.caption.upsert({
      where: { contentPieceId_platform: { contentPieceId: piece.id, platform } },
      create: {
        contentPieceId: piece.id,
        platform,
        text: optimized.text,
        hashtags: optimized.hashtags,
        characterCount: optimized.characterCount,
        withinLimit: optimized.withinLimit,
      },
      update: {
        text: optimized.text,
        hashtags: optimized.hashtags,
        characterCount: optimized.characterCount,
        withinLimit: optimized.withinLimit,
      },
    });

    const media = await prisma.mediaAsset.findMany({
      where: { contentPieceId: piece.id, kind: { in: ['image', 'video'] } },
    });
    if (media.length > 0) {
      targets.push({
        platform,
        input: {
          kind: format === 'CAROUSEL' ? 'CAROUSEL' : 'REEL',
          caption: optimized.text,
          media: media.map((m) => ({
            url: m.publicUrl,
            kind: m.kind === 'video' ? ('VIDEO' as const) : ('IMAGE' as const),
            mimeType: m.mimeType,
            ...(m.width ? { width: m.width } : {}),
            ...(m.height ? { height: m.height } : {}),
            ...(m.fileSizeBytes ? { fileSizeBytes: m.fileSizeBytes } : {}),
          })),
        },
      });
    }
  }

  const platformVerdicts = runPlatformQa(targets);
  const assets = await prisma.mediaAsset.findMany({ where: { contentPieceId: piece.id } });
  const rights = assessPostRights(
    assets.map((a) => ({
      assetSource: a.assetSource,
      ...(a.sourceUrl ? { sourceUrl: a.sourceUrl } : {}),
      ...(a.license ? { license: a.license } : {}),
      attributionRequired: a.attributionRequired,
      ...(a.attributionText ? { attributionText: a.attributionText } : {}),
    })),
  );

  const decision = decidePublish({
    safety,
    brand,
    platformVerdicts: platformVerdicts.map((p) => ({ platform: p.platform, verdict: p.verdict, issues: p.issues })),
    rightsPublishable: rights.publishable,
    factGateAllowed: factGate.allowed,
    ...(factGate.reason ? { factGateReason: factGate.reason } : {}),
    autonomousMode: state.autonomousMode,
  });

  const reasons = [...decision.reasons];
  // A near-duplicate is not a safety issue but is a real quality failure —
  // the audience experiences it as the account repeating itself.
  if (duplicate) reasons.push('Too similar to recently published content.');

  for (const [gate, result] of [
    ['SAFETY', { verdict: safety.verdict, findings: safety.findings }],
    ['BRAND', { verdict: brand.verdict, findings: brand.findings }],
  ] as const) {
    await prisma.qaResult.create({
      data: {
        contentPieceId: piece.id,
        gate,
        verdict: result.verdict,
        findings: result.findings as unknown as object,
        ...(gate === 'BRAND' ? { score: brand.score } : {}),
      },
    });
  }
  for (const verdict of platformVerdicts) {
    await prisma.qaResult.create({
      data: {
        contentPieceId: piece.id,
        gate: 'PLATFORM',
        verdict: verdict.verdict,
        platform: verdict.platform,
        findings: verdict.issues as unknown as object,
      },
    });
  }

  const approved = decision.decision === 'APPROVE' && !duplicate;
  const viralPotential = computeViralPotential({
    topicScore: topic.compositeScore ?? 50,
    hookScore: hookResult.selected.composite,
    visualScore: brand.score,
    audienceMatch: brand.score,
  });

  await prisma.contentPiece.update({
    where: { id: piece.id },
    data: {
      status: approved ? 'APPROVED' : 'FLAGGED',
      qualityScore: brand.score,
      viralPotentialScore: viralPotential,
      ...(approved
        ? { approvedAt: new Date(), approvedBy: 'system' }
        : { flagReason: reasons.join(' '), flaggedAt: new Date() }),
    },
  });

  await prisma.contentStatusChange.create({
    data: {
      contentPieceId: piece.id,
      fromStatus: 'QA',
      toStatus: approved ? 'APPROVED' : 'FLAGGED',
      reason: reasons.join(' '),
    },
  });
  await prisma.topic.update({ where: { id: topicId }, data: { status: 'USED' } });

  log.info(
    { contentPieceId: piece.id, decision: decision.decision, duplicate, imageCostUsd },
    'generation complete',
  );

  return {
    contentPieceId: piece.id,
    status: approved ? 'APPROVED' : 'FLAGGED',
    format,
    reasons,
  };
}
