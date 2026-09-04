/**
 * Application context: every shared dependency, constructed once at boot.
 *
 * Providers are constructed lazily and their failures captured rather than
 * thrown, so a missing TikTok credential degrades that one integration instead
 * of preventing the server from starting. `integrations` then tells the
 * dashboard exactly what is wired up, which is what lets the UI disable a
 * control and explain why rather than offering a button that throws.
 */
import { getConfig, configuredIntegrations, createLogger, Encryptor, type Config, type Logger } from '@mmos/core';
import { TokenStore, prisma } from '@mmos/db';
import { AdapterRegistry } from '@mmos/platforms';
import { AiOrchestrator, createLlmProvider, createSearchProviders, type LlmProvider, type SearchProvider } from '@mmos/ai';
import { AnalyticsService, AutomationService, DbCostSink, PublishingService, QueueRegistry } from '@mmos/engine';

export interface AppContext {
  config: Config;
  logger: Logger;
  encryptor: Encryptor;
  tokens: TokenStore;
  adapters: AdapterRegistry;
  automation: AutomationService;
  publishing: PublishingService;
  analytics: AnalyticsService;
  llm: LlmProvider | null;
  searchProviders: SearchProvider[];
  integrations: ReturnType<typeof configuredIntegrations>;
  /** Null when Redis is unreachable; endpoints that enqueue say so explicitly. */
  queues: QueueRegistry | null;
  /** Why an integration is unavailable, surfaced verbatim in the UI. */
  integrationErrors: Record<string, string>;
  orchestratorFor(organizationId: string): AiOrchestrator;
}

export function createContext(config: Config = getConfig()): AppContext {
  const logger = createLogger({
    level: config.LOG_LEVEL,
    name: 'mmos-api',
    pretty: config.NODE_ENV === 'development',
  });

  const encryptor = new Encryptor(config.ENCRYPTION_KEY);
  const tokens = new TokenStore(config.ENCRYPTION_KEY);
  const adapters = new AdapterRegistry(config);
  const automation = new AutomationService(logger);
  const integrationErrors: Record<string, string> = {};

  let llm: LlmProvider | null = null;
  try {
    llm = createLlmProvider(config);
  } catch (err) {
    integrationErrors['llm'] = (err as Error).message;
    logger.warn({ err }, 'LLM provider not configured; content generation is unavailable');
  }

  let searchProviders: SearchProvider[] = [];
  try {
    searchProviders = createSearchProviders(config, logger);
  } catch (err) {
    integrationErrors['search'] = (err as Error).message;
    logger.warn({ err }, 'no research provider configured; trend discovery is unavailable');
  }

  // The API enqueues work for the worker (manual runs, publish retries). A
  // Redis failure must not prevent the server from starting — read-only routes
  // still work, and the enqueueing routes report the outage plainly.
  let queues: QueueRegistry | null = null;
  try {
    queues = new QueueRegistry(config.REDIS_URL);
  } catch (err) {
    integrationErrors['queue'] = (err as Error).message;
    logger.error({ err }, 'could not connect to Redis; manual runs and retries are unavailable');
  }

  const publishing = new PublishingService({ adapters, tokens, automation, logger });
  const analytics = new AnalyticsService({ adapters, tokens, logger });

  return {
    config,
    logger,
    encryptor,
    tokens,
    adapters,
    automation,
    publishing,
    analytics,
    llm,
    searchProviders,
    integrations: configuredIntegrations(config),
    queues,
    integrationErrors,
    orchestratorFor(organizationId: string): AiOrchestrator {
      if (!llm) throw new Error(integrationErrors['llm'] ?? 'No LLM provider configured');
      return new AiOrchestrator({
        llm,
        costSink: new DbCostSink(organizationId),
        logger,
        dailyLimitUsd: config.DAILY_COST_LIMIT_USD,
        monthlyLimitUsd: config.MONTHLY_COST_LIMIT_USD,
      });
    },
  };
}

export { prisma };
