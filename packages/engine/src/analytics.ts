/**
 * Analytics collection and normalization.
 *
 * The important discipline: a metric a platform will not return is stored as
 * NULL and named in `unavailableMetrics` — never as 0. A fabricated zero would
 * flow into the learning engine and be indistinguishable from genuinely poor
 * performance, quietly corrupting every downstream decision.
 */
import { prisma, TokenStore } from '@mmos/db';
import { PlatformAuthError, type Logger } from '@mmos/core';
import { AdapterRegistry, type PlatformName } from '@mmos/platforms';

export interface AnalyticsDeps {
  adapters: AdapterRegistry;
  tokens: TokenStore;
  logger: Logger;
}

export class AnalyticsService {
  constructor(private readonly deps: AnalyticsDeps) {}

  /**
   * Collects analytics for published posts. Skips posts younger than
   * `minAgeMinutes` — platform metrics are not meaningful immediately after
   * publishing, and recording a near-zero would misinform the learning engine.
   */
  async collectForOrganization(
    organizationId: string,
    { minAgeMinutes = 60, limit = 50 }: { minAgeMinutes?: number; limit?: number } = {},
  ): Promise<{ collected: number; failed: number }> {
    const cutoff = new Date(Date.now() - minAgeMinutes * 60_000);
    const jobs = await prisma.publishingJob.findMany({
      where: {
        status: 'PUBLISHED',
        platformPostId: { not: null },
        publishedAt: { lte: cutoff },
        socialAccount: { organizationId, status: 'CONNECTED' },
      },
      include: { socialAccount: true },
      orderBy: { publishedAt: 'desc' },
      take: limit,
    });

    let collected = 0;
    let failed = 0;

    for (const job of jobs) {
      try {
        const token = await this.deps.tokens.get(job.socialAccountId);
        if (!token) throw new PlatformAuthError(job.platform, 'No stored credentials');

        const adapter = this.deps.adapters.get(job.platform as PlatformName);
        const metrics = await adapter.getAnalytics(
          { accessToken: token.accessToken, platformAccountId: job.socialAccount.platformAccountId },
          job.platformPostId as string,
        );

        await prisma.analyticsRecord.create({
          data: {
            socialAccountId: job.socialAccountId,
            publishingJobId: job.id,
            platform: job.platform,
            platformPostId: metrics.platformPostId,
            collectedAt: metrics.collectedAt,
            views: metrics.views,
            reach: metrics.reach,
            impressions: metrics.impressions,
            likes: metrics.likes,
            comments: metrics.comments,
            shares: metrics.shares,
            saves: metrics.saves,
            watchTimeSec: metrics.watchTimeSec,
            avgWatchTimeSec: metrics.avgWatchTimeSec,
            retentionRate: metrics.retentionRate,
            profileVisits: metrics.profileVisits,
            followsGained: metrics.followsGained,
            clicks: metrics.clicks,
            engagementRate: metrics.engagementRate,
            unavailableMetrics: metrics.unavailableMetrics,
            raw: metrics.raw ? JSON.parse(JSON.stringify(metrics.raw)) : undefined,
          },
        });

        await prisma.contentPiece.updateMany({
          where: { id: job.contentPieceId, status: 'PUBLISHED' },
          data: { status: 'ANALYZING' },
        });

        collected++;
      } catch (err) {
        failed++;
        this.deps.logger.warn({ err, jobId: job.id, platform: job.platform }, 'analytics collection failed');
        if (err instanceof PlatformAuthError) {
          await prisma.socialAccount.update({
            where: { id: job.socialAccountId },
            data: { status: 'TOKEN_EXPIRED', statusMessage: (err as Error).message },
          });
        }
      }
    }

    return { collected, failed };
  }

  /** Daily account-level snapshot, for follower growth and reach over time. */
  async snapshotAccounts(organizationId: string): Promise<number> {
    const accounts = await prisma.socialAccount.findMany({
      where: { organizationId, status: 'CONNECTED' },
    });

    let count = 0;
    for (const account of accounts) {
      try {
        const token = await this.deps.tokens.get(account.id);
        if (!token) continue;
        const adapter = this.deps.adapters.get(account.platform as PlatformName);
        const stats = await adapter.getAccountAnalytics({
          accessToken: token.accessToken,
          platformAccountId: account.platformAccountId,
        });

        const publishedToday = await prisma.publishingJob.count({
          where: {
            socialAccountId: account.id,
            status: 'PUBLISHED',
            publishedAt: { gte: new Date(Date.now() - 86_400_000) },
          },
        });

        await prisma.performanceSnapshot.create({
          data: {
            socialAccountId: account.id,
            followerCount: stats.followerCount,
            reach: stats.reach,
            views: stats.views,
            postsPublished: publishedToday,
          },
        });
        if (stats.followerCount !== null) {
          await prisma.socialAccount.update({
            where: { id: account.id },
            data: { followerCount: stats.followerCount, lastSyncAt: new Date() },
          });
        }
        count++;
      } catch (err) {
        this.deps.logger.warn({ err, accountId: account.id }, 'account snapshot failed');
      }
    }
    return count;
  }

  /**
   * Unified cross-platform rollup for the dashboard. Metric totals sum only
   * platforms that actually reported them, and the response names which
   * platforms could not supply each metric.
   */
  async summary(organizationId: string, since: Date): Promise<{
    totals: Record<string, number | null>;
    byPlatform: Array<{ platform: string; views: number | null; reach: number | null; engagementRate: number | null; posts: number }>;
    unavailable: Record<string, string[]>;
  }> {
    const records = await prisma.analyticsRecord.findMany({
      where: { socialAccount: { organizationId }, collectedAt: { gte: since } },
      orderBy: { collectedAt: 'desc' },
    });

    const metricKeys = ['views', 'reach', 'likes', 'comments', 'shares', 'saves', 'followsGained'] as const;
    const totals: Record<string, number | null> = {};
    for (const key of metricKeys) {
      const present = records.map((r) => r[key]).filter((v): v is number => v !== null);
      totals[key] = present.length > 0 ? present.reduce((a, b) => a + b, 0) : null;
    }

    const platforms = new Map<string, typeof records>();
    for (const r of records) {
      const list = platforms.get(r.platform) ?? [];
      list.push(r);
      platforms.set(r.platform, list);
    }

    const byPlatform = [...platforms.entries()].map(([platform, rows]) => {
      const num = (key: 'views' | 'reach') => {
        const present = rows.map((r) => r[key]).filter((v): v is number => v !== null);
        return present.length > 0 ? present.reduce((a, b) => a + b, 0) : null;
      };
      const rates = rows.map((r) => r.engagementRate).filter((v): v is number => v !== null);
      return {
        platform,
        views: num('views'),
        reach: num('reach'),
        engagementRate: rates.length > 0 ? rates.reduce((a, b) => a + b, 0) / rates.length : null,
        posts: rows.length,
      };
    });

    // So the UI can say "this platform does not report saves" rather than 0.
    const unavailable: Record<string, string[]> = {};
    for (const [platform, rows] of platforms) {
      unavailable[platform] = [...new Set(rows.flatMap((r) => r.unavailableMetrics))];
    }

    return { totals, byPlatform, unavailable };
  }
}
