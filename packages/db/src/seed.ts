/**
 * Seeds the default brand and automation state for the existing organization.
 *
 * Deliberately does NOT create fake topics, content, or analytics. A dashboard
 * showing invented numbers would violate the core rule of this project — you
 * must be able to trust what it says.
 */
// Must precede the client import, which reads DATABASE_URL as it loads.
import '@mmos/core/env';
import { DEFAULT_BRAND, DEFAULT_CONTENT_MIX, DEFAULT_SCORING_WEIGHTS, BRAND_COLORS } from '@mmos/core';
import { prisma } from './client.js';

async function main(): Promise<void> {
  const organization = await prisma.organization.findFirst();
  if (!organization) {
    console.error(
      'No organization found. Register the first user through the dashboard or POST /api/auth/register, then run this again.',
    );
    process.exit(1);
  }

  const brand = await prisma.brand.upsert({
    where: { id: `${organization.id}-default` },
    create: {
      id: `${organization.id}-default`,
      organizationId: organization.id,
      name: DEFAULT_BRAND.name,
      colors: BRAND_COLORS,
      fonts: DEFAULT_BRAND.fonts,
      tone: [...DEFAULT_BRAND.tone],
      avoidList: [...DEFAULT_BRAND.avoid],
      visualDirection: DEFAULT_BRAND.visualDirection,
      defaultSlideCount: DEFAULT_BRAND.defaultSlideCount,
      aspectRatios: DEFAULT_BRAND.aspectRatios,
      contentMix: DEFAULT_CONTENT_MIX,
      scoringWeights: DEFAULT_SCORING_WEIGHTS,
      isDefault: true,
    },
    update: {},
  });

  await prisma.automationState.upsert({
    where: { organizationId: organization.id },
    create: {
      organizationId: organization.id,
      // Autonomous mode starts OFF. It is switched on deliberately, after the
      // operator has seen what the system produces.
      autonomousMode: false,
      agentFlags: {
        trendHunter: true, topicScorer: true, researcher: true, factChecker: true,
        strategist: true, hookEngine: true, carouselWriter: true, carouselDesigner: true,
        reelWriter: true, reelProducer: true, mediaSourcing: true, qualityControl: true,
        publisher: true, analytics: true, learningEngine: true,
      },
    },
    update: {},
  });

  const prompts = await prisma.prompt.count();
  console.log(`Seeded brand "${brand.name}" and automation state for ${organization.name}.`);
  console.log(`Prompts in database: ${prompts} (agent prompts are versioned in packages/agents/src/prompts.ts).`);
  console.log('\nAutonomous mode is OFF. Connect accounts and review output before enabling it.');
}

main()
  .catch((err) => {
    console.error(err);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
