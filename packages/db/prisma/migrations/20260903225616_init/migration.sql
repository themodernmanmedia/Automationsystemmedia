-- CreateEnum
CREATE TYPE "Role" AS ENUM ('OWNER', 'ADMIN', 'EDITOR', 'VIEWER');

-- CreateEnum
CREATE TYPE "Platform" AS ENUM ('INSTAGRAM', 'TIKTOK', 'FACEBOOK', 'YOUTUBE', 'X', 'LINKEDIN', 'PINTEREST', 'THREADS');

-- CreateEnum
CREATE TYPE "AccountStatus" AS ENUM ('CONNECTED', 'TOKEN_EXPIRED', 'REVOKED', 'ERROR', 'DISCONNECTED');

-- CreateEnum
CREATE TYPE "TopicStatus" AS ENUM ('DISCOVERED', 'SCORED', 'SELECTED', 'RESEARCHING', 'RESEARCHED', 'IN_PRODUCTION', 'USED', 'REJECTED', 'EXPIRED');

-- CreateEnum
CREATE TYPE "ContentCategory" AS ENUM ('MONEY', 'BUSINESS', 'AI', 'TECHNOLOGY', 'MINDSET', 'PSYCHOLOGY', 'SPORTS', 'LUXURY', 'LIFESTYLE', 'RELATIONSHIPS', 'NEWS');

-- CreateEnum
CREATE TYPE "VerificationStatus" AS ENUM ('VERIFIED', 'PARTIALLY_VERIFIED', 'UNVERIFIED', 'CONTRADICTED');

-- CreateEnum
CREATE TYPE "ContentFormat" AS ENUM ('CAROUSEL', 'REEL', 'SINGLE_IMAGE', 'STORY', 'SERIES');

-- CreateEnum
CREATE TYPE "ContentStatus" AS ENUM ('DISCOVERED', 'RESEARCHING', 'RESEARCHED', 'WRITING', 'DESIGNING', 'QA', 'APPROVED', 'SCHEDULED', 'PUBLISHING', 'PUBLISHED', 'ANALYZING', 'LEARNED', 'FLAGGED', 'FAILED', 'ARCHIVED');

-- CreateEnum
CREATE TYPE "AssetSource" AS ENUM ('GENERATED', 'STOCK_LICENSED', 'PUBLIC_DOMAIN', 'ORIGINAL', 'BRAND_ASSET');

-- CreateEnum
CREATE TYPE "RightsRisk" AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'UNKNOWN');

-- CreateEnum
CREATE TYPE "QaGate" AS ENUM ('BRAND', 'PLATFORM', 'SAFETY', 'RIGHTS', 'FACT', 'DUPLICATE');

-- CreateEnum
CREATE TYPE "QaVerdict" AS ENUM ('PASS', 'WARN', 'FAIL');

-- CreateEnum
CREATE TYPE "PublishingJobStatus" AS ENUM ('QUEUED', 'SCHEDULED', 'PUBLISHING', 'PUBLISHED', 'FAILED', 'CANCELLED', 'BLOCKED');

-- CreateEnum
CREATE TYPE "ExperimentStatus" AS ENUM ('DRAFT', 'RUNNING', 'COMPLETE', 'ABANDONED');

-- CreateEnum
CREATE TYPE "AgentRunStatus" AS ENUM ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED');

-- CreateTable
CREATE TABLE "organizations" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "organizations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "users" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "role" "Role" NOT NULL DEFAULT 'VIEWER',
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "lastLoginAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "revokedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "brands" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "logoUrl" TEXT,
    "watermarkUrl" TEXT,
    "colors" JSONB NOT NULL,
    "fonts" JSONB NOT NULL,
    "tone" TEXT[],
    "avoidList" TEXT[],
    "ctaStyle" TEXT NOT NULL DEFAULT 'Follow @themodernman for more.',
    "visualDirection" TEXT NOT NULL DEFAULT 'luxury magazine x business media x modern menswear editorial',
    "defaultSlideCount" INTEGER NOT NULL DEFAULT 8,
    "aspectRatios" JSONB NOT NULL,
    "voicePreferences" JSONB,
    "visualPreferences" JSONB,
    "contentMix" JSONB NOT NULL,
    "scoringWeights" JSONB NOT NULL,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "brands_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "social_accounts" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "brandId" TEXT,
    "platform" "Platform" NOT NULL,
    "platformAccountId" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "displayName" TEXT,
    "profileImageUrl" TEXT,
    "accountType" TEXT,
    "status" "AccountStatus" NOT NULL DEFAULT 'CONNECTED',
    "statusMessage" TEXT,
    "isAudited" BOOLEAN NOT NULL DEFAULT false,
    "scopes" TEXT[],
    "lastSyncAt" TIMESTAMP(3),
    "lastPublishAt" TIMESTAMP(3),
    "lastPublishError" TEXT,
    "followerCount" INTEGER,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "social_accounts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "platform_tokens" (
    "id" TEXT NOT NULL,
    "socialAccountId" TEXT NOT NULL,
    "accessTokenEnc" TEXT NOT NULL,
    "refreshTokenEnc" TEXT,
    "tokenType" TEXT NOT NULL DEFAULT 'bearer',
    "expiresAt" TIMESTAMP(3),
    "refreshExpiresAt" TIMESTAMP(3),
    "scopes" TEXT[],
    "lastRefreshedAt" TIMESTAMP(3),
    "refreshFailures" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "platform_tokens_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "topics" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "brandId" TEXT,
    "title" TEXT NOT NULL,
    "summary" TEXT NOT NULL,
    "category" "ContentCategory" NOT NULL,
    "status" "TopicStatus" NOT NULL DEFAULT 'DISCOVERED',
    "discoverySource" TEXT NOT NULL,
    "discoveryUrl" TEXT,
    "keywords" TEXT[],
    "entities" TEXT[],
    "dimensionScores" JSONB,
    "compositeScore" DOUBLE PRECISION,
    "viralPotential" DOUBLE PRECISION,
    "scoredAt" TIMESTAMP(3),
    "contentHash" TEXT,
    "embedding" DOUBLE PRECISION[],
    "isBreakingNews" BOOLEAN NOT NULL DEFAULT false,
    "expiresAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "topics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sources" (
    "id" TEXT NOT NULL,
    "topicId" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "publisher" TEXT,
    "author" TEXT,
    "publishedAt" TIMESTAMP(3),
    "retrievedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "excerpt" TEXT,
    "fullText" TEXT,
    "credibility" DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sources_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "claims" (
    "id" TEXT NOT NULL,
    "topicId" TEXT NOT NULL,
    "sourceId" TEXT,
    "text" TEXT NOT NULL,
    "claimType" TEXT NOT NULL,
    "verification" "VerificationStatus" NOT NULL DEFAULT 'UNVERIFIED',
    "confidence" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "corroborationCount" INTEGER NOT NULL DEFAULT 0,
    "verifierNotes" TEXT,
    "verifiedAt" TIMESTAMP(3),
    "sourceUrl" TEXT,
    "sourceDate" TIMESTAMP(3),
    "retrievedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "claims_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "research_reports" (
    "id" TEXT NOT NULL,
    "topicId" TEXT NOT NULL,
    "summary" TEXT NOT NULL,
    "keyFindings" TEXT[],
    "angles" TEXT[],
    "statistics" JSONB,
    "people" TEXT[],
    "companies" TEXT[],
    "quotes" JSONB,
    "contradictions" TEXT[],
    "sourceCount" INTEGER NOT NULL DEFAULT 0,
    "claimCount" INTEGER NOT NULL DEFAULT 0,
    "verifiedCount" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "research_reports_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "content_ideas" (
    "id" TEXT NOT NULL,
    "topicId" TEXT NOT NULL,
    "format" "ContentFormat" NOT NULL,
    "angle" TEXT NOT NULL,
    "hook" TEXT NOT NULL,
    "rationale" TEXT,
    "targetPlatforms" "Platform"[],
    "score" DOUBLE PRECISION,
    "selected" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "content_ideas_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "content_pieces" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "brandId" TEXT,
    "topicId" TEXT,
    "contentIdeaId" TEXT,
    "format" "ContentFormat" NOT NULL,
    "status" "ContentStatus" NOT NULL DEFAULT 'DISCOVERED',
    "category" "ContentCategory" NOT NULL,
    "title" TEXT NOT NULL,
    "hook" TEXT NOT NULL,
    "hookArchetype" TEXT,
    "scriptBody" TEXT,
    "cta" TEXT,
    "designNotes" JSONB,
    "viralPotentialScore" DOUBLE PRECISION,
    "qualityScore" DOUBLE PRECISION,
    "flagReason" TEXT,
    "flaggedAt" TIMESTAMP(3),
    "approvedAt" TIMESTAMP(3),
    "approvedBy" TEXT,
    "contentHash" TEXT,
    "embedding" DOUBLE PRECISION[],
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "content_pieces_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "content_status_changes" (
    "id" TEXT NOT NULL,
    "contentPieceId" TEXT NOT NULL,
    "fromStatus" "ContentStatus",
    "toStatus" "ContentStatus" NOT NULL,
    "reason" TEXT,
    "actor" TEXT NOT NULL DEFAULT 'system',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "content_status_changes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "carousel_posts" (
    "id" TEXT NOT NULL,
    "contentPieceId" TEXT NOT NULL,
    "slideCount" INTEGER NOT NULL,
    "aspectRatio" TEXT NOT NULL DEFAULT '4:5',
    "coverSlideIndex" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "carousel_posts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "carousel_slides" (
    "id" TEXT NOT NULL,
    "carouselPostId" TEXT NOT NULL,
    "position" INTEGER NOT NULL,
    "headline" TEXT,
    "body" TEXT,
    "slideRole" TEXT NOT NULL,
    "design" JSONB NOT NULL,
    "renderedImageUrl" TEXT,
    "mediaAssetId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "carousel_slides_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "reels" (
    "id" TEXT NOT NULL,
    "contentPieceId" TEXT NOT NULL,
    "durationSec" DOUBLE PRECISION,
    "aspectRatio" TEXT NOT NULL DEFAULT '9:16',
    "width" INTEGER NOT NULL DEFAULT 1080,
    "height" INTEGER NOT NULL DEFAULT 1920,
    "scriptBeats" JSONB NOT NULL,
    "voiceoverText" TEXT,
    "renderedVideoUrl" TEXT,
    "thumbnailUrl" TEXT,
    "renderStatus" TEXT NOT NULL DEFAULT 'PENDING',
    "renderError" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "reels_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "media_assets" (
    "id" TEXT NOT NULL,
    "contentPieceId" TEXT,
    "kind" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "publicUrl" TEXT NOT NULL,
    "mimeType" TEXT NOT NULL,
    "width" INTEGER,
    "height" INTEGER,
    "durationSec" DOUBLE PRECISION,
    "fileSizeBytes" INTEGER,
    "assetSource" "AssetSource" NOT NULL,
    "sourceUrl" TEXT,
    "creator" TEXT,
    "license" TEXT,
    "licenseUrl" TEXT,
    "attributionRequired" BOOLEAN NOT NULL DEFAULT false,
    "attributionText" TEXT,
    "rightsRisk" "RightsRisk" NOT NULL DEFAULT 'UNKNOWN',
    "rightsNotes" TEXT,
    "generationPrompt" TEXT,
    "generationModel" TEXT,
    "contentHash" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "media_assets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "audio_assets" (
    "id" TEXT NOT NULL,
    "reelId" TEXT,
    "kind" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "publicUrl" TEXT NOT NULL,
    "mimeType" TEXT NOT NULL,
    "durationSec" DOUBLE PRECISION,
    "assetSource" "AssetSource" NOT NULL,
    "license" TEXT,
    "rightsRisk" "RightsRisk" NOT NULL DEFAULT 'UNKNOWN',
    "voiceProvider" TEXT,
    "voiceId" TEXT,
    "transcript" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "audio_assets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "captions" (
    "id" TEXT NOT NULL,
    "contentPieceId" TEXT NOT NULL,
    "platform" "Platform" NOT NULL,
    "text" TEXT NOT NULL,
    "hashtags" TEXT[],
    "characterCount" INTEGER NOT NULL,
    "withinLimit" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "captions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "hashtags" (
    "id" TEXT NOT NULL,
    "tag" TEXT NOT NULL,
    "category" "ContentCategory",
    "useCount" INTEGER NOT NULL DEFAULT 0,
    "lastUsedAt" TIMESTAMP(3),
    "avgEngagement" DOUBLE PRECISION,
    "isBanned" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "hashtags_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "qa_results" (
    "id" TEXT NOT NULL,
    "contentPieceId" TEXT NOT NULL,
    "gate" "QaGate" NOT NULL,
    "verdict" "QaVerdict" NOT NULL,
    "score" DOUBLE PRECISION,
    "findings" JSONB NOT NULL,
    "platform" "Platform",
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "qa_results_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "content_scores" (
    "id" TEXT NOT NULL,
    "contentPieceId" TEXT NOT NULL,
    "scoreType" TEXT NOT NULL,
    "value" DOUBLE PRECISION NOT NULL,
    "breakdown" JSONB,
    "scorerVersion" TEXT NOT NULL DEFAULT 'v1',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "content_scores_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "publishing_jobs" (
    "id" TEXT NOT NULL,
    "contentPieceId" TEXT NOT NULL,
    "socialAccountId" TEXT NOT NULL,
    "platform" "Platform" NOT NULL,
    "status" "PublishingJobStatus" NOT NULL DEFAULT 'QUEUED',
    "scheduledAt" TIMESTAMP(3) NOT NULL,
    "publishedAt" TIMESTAMP(3),
    "scheduleStrategy" TEXT NOT NULL DEFAULT 'SELF_TIMED',
    "platformPostId" TEXT,
    "platformUrl" TEXT,
    "platformContainerId" TEXT,
    "attemptCount" INTEGER NOT NULL DEFAULT 0,
    "lastError" TEXT,
    "lastErrorCode" TEXT,
    "blockedReason" TEXT,
    "idempotencyKey" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "publishing_jobs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "publishing_attempts" (
    "id" TEXT NOT NULL,
    "publishingJobId" TEXT NOT NULL,
    "attemptNumber" INTEGER NOT NULL,
    "step" TEXT NOT NULL,
    "success" BOOLEAN NOT NULL,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "httpStatus" INTEGER,
    "requestSummary" JSONB,
    "responseBody" JSONB,
    "durationMs" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "publishing_attempts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "analytics_records" (
    "id" TEXT NOT NULL,
    "socialAccountId" TEXT NOT NULL,
    "publishingJobId" TEXT,
    "platform" "Platform" NOT NULL,
    "platformPostId" TEXT NOT NULL,
    "collectedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "views" INTEGER,
    "reach" INTEGER,
    "impressions" INTEGER,
    "likes" INTEGER,
    "comments" INTEGER,
    "shares" INTEGER,
    "saves" INTEGER,
    "watchTimeSec" DOUBLE PRECISION,
    "avgWatchTimeSec" DOUBLE PRECISION,
    "retentionRate" DOUBLE PRECISION,
    "profileVisits" INTEGER,
    "followsGained" INTEGER,
    "clicks" INTEGER,
    "engagementRate" DOUBLE PRECISION,
    "unavailableMetrics" TEXT[],
    "raw" JSONB,

    CONSTRAINT "analytics_records_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "performance_snapshots" (
    "id" TEXT NOT NULL,
    "socialAccountId" TEXT NOT NULL,
    "capturedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "followerCount" INTEGER,
    "reach" INTEGER,
    "views" INTEGER,
    "engagementRate" DOUBLE PRECISION,
    "postsPublished" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "performance_snapshots_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "learning_insights" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "dimension" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "sampleSize" INTEGER NOT NULL,
    "avgEngagement" DOUBLE PRECISION NOT NULL,
    "avgReach" DOUBLE PRECISION,
    "avgSaves" DOUBLE PRECISION,
    "avgWatchTime" DOUBLE PRECISION,
    "liftVsBaseline" DOUBLE PRECISION NOT NULL,
    "confidence" DOUBLE PRECISION NOT NULL,
    "windowStart" TIMESTAMP(3) NOT NULL,
    "windowEnd" TIMESTAMP(3) NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "learning_insights_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "experiments" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "hypothesis" TEXT NOT NULL,
    "variable" TEXT NOT NULL,
    "variants" JSONB NOT NULL,
    "status" "ExperimentStatus" NOT NULL DEFAULT 'DRAFT',
    "minSampleSize" INTEGER NOT NULL DEFAULT 10,
    "results" JSONB,
    "winner" TEXT,
    "conclusion" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "experiments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "system_memories" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "memoryType" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "value" JSONB NOT NULL,
    "weight" DOUBLE PRECISION NOT NULL DEFAULT 1,
    "observations" INTEGER NOT NULL DEFAULT 1,
    "lastObservedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "system_memories_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "prompts" (
    "id" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "version" INTEGER NOT NULL DEFAULT 1,
    "systemPrompt" TEXT NOT NULL,
    "userTemplate" TEXT NOT NULL,
    "model" TEXT,
    "temperature" DOUBLE PRECISION NOT NULL DEFAULT 0.7,
    "maxTokens" INTEGER NOT NULL DEFAULT 4000,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "prompts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "agent_runs" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "agentName" TEXT NOT NULL,
    "status" "AgentRunStatus" NOT NULL DEFAULT 'RUNNING',
    "trigger" TEXT NOT NULL,
    "inputSummary" JSONB,
    "outputSummary" JSONB,
    "itemsProcessed" INTEGER NOT NULL DEFAULT 0,
    "itemsProduced" INTEGER NOT NULL DEFAULT 0,
    "model" TEXT,
    "inputTokens" INTEGER,
    "outputTokens" INTEGER,
    "costUsd" DOUBLE PRECISION,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finishedAt" TIMESTAMP(3),
    "durationMs" INTEGER,

    CONSTRAINT "agent_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "agent_errors" (
    "id" TEXT NOT NULL,
    "agentRunId" TEXT NOT NULL,
    "errorCode" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "stack" TEXT,
    "context" JSONB,
    "retryable" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "agent_errors_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "cost_entries" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "topicId" TEXT,
    "contentPieceId" TEXT,
    "service" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "model" TEXT,
    "operation" TEXT NOT NULL,
    "inputTokens" INTEGER,
    "outputTokens" INTEGER,
    "units" DOUBLE PRECISION,
    "costUsd" DOUBLE PRECISION NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "cost_entries_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "automation_states" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "autonomousMode" BOOLEAN NOT NULL DEFAULT false,
    "killSwitch" BOOLEAN NOT NULL DEFAULT false,
    "publishingPaused" BOOLEAN NOT NULL DEFAULT false,
    "agentFlags" JSONB NOT NULL,
    "minQueueHours" INTEGER NOT NULL DEFAULT 24,
    "targetQueueHours" INTEGER NOT NULL DEFAULT 72,
    "maxQueueHours" INTEGER NOT NULL DEFAULT 168,
    "maxPostsPerDay" INTEGER NOT NULL DEFAULT 8,
    "lastTrendScanAt" TIMESTAMP(3),
    "lastGenerationAt" TIMESTAMP(3),
    "lastAnalyticsAt" TIMESTAMP(3),
    "lastLearningAt" TIMESTAMP(3),
    "pausedBy" TEXT,
    "pausedAt" TIMESTAMP(3),
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "automation_states_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "audit_logs" (
    "id" TEXT NOT NULL,
    "organizationId" TEXT NOT NULL,
    "actorType" TEXT NOT NULL,
    "actorId" TEXT,
    "action" TEXT NOT NULL,
    "subjectType" TEXT,
    "subjectId" TEXT,
    "diff" JSONB,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "audit_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "organizations_slug_key" ON "organizations"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE INDEX "users_organizationId_idx" ON "users"("organizationId");

-- CreateIndex
CREATE UNIQUE INDEX "sessions_tokenHash_key" ON "sessions"("tokenHash");

-- CreateIndex
CREATE INDEX "sessions_userId_idx" ON "sessions"("userId");

-- CreateIndex
CREATE INDEX "sessions_expiresAt_idx" ON "sessions"("expiresAt");

-- CreateIndex
CREATE INDEX "brands_organizationId_idx" ON "brands"("organizationId");

-- CreateIndex
CREATE INDEX "social_accounts_organizationId_idx" ON "social_accounts"("organizationId");

-- CreateIndex
CREATE UNIQUE INDEX "social_accounts_organizationId_platform_platformAccountId_key" ON "social_accounts"("organizationId", "platform", "platformAccountId");

-- CreateIndex
CREATE UNIQUE INDEX "platform_tokens_socialAccountId_key" ON "platform_tokens"("socialAccountId");

-- CreateIndex
CREATE INDEX "platform_tokens_expiresAt_idx" ON "platform_tokens"("expiresAt");

-- CreateIndex
CREATE INDEX "topics_organizationId_status_idx" ON "topics"("organizationId", "status");

-- CreateIndex
CREATE INDEX "topics_organizationId_category_idx" ON "topics"("organizationId", "category");

-- CreateIndex
CREATE INDEX "topics_compositeScore_idx" ON "topics"("compositeScore");

-- CreateIndex
CREATE INDEX "topics_contentHash_idx" ON "topics"("contentHash");

-- CreateIndex
CREATE INDEX "sources_topicId_idx" ON "sources"("topicId");

-- CreateIndex
CREATE INDEX "claims_topicId_idx" ON "claims"("topicId");

-- CreateIndex
CREATE INDEX "claims_verification_idx" ON "claims"("verification");

-- CreateIndex
CREATE INDEX "research_reports_topicId_idx" ON "research_reports"("topicId");

-- CreateIndex
CREATE INDEX "content_ideas_topicId_idx" ON "content_ideas"("topicId");

-- CreateIndex
CREATE INDEX "content_pieces_organizationId_status_idx" ON "content_pieces"("organizationId", "status");

-- CreateIndex
CREATE INDEX "content_pieces_organizationId_format_idx" ON "content_pieces"("organizationId", "format");

-- CreateIndex
CREATE INDEX "content_pieces_contentHash_idx" ON "content_pieces"("contentHash");

-- CreateIndex
CREATE INDEX "content_status_changes_contentPieceId_idx" ON "content_status_changes"("contentPieceId");

-- CreateIndex
CREATE UNIQUE INDEX "carousel_posts_contentPieceId_key" ON "carousel_posts"("contentPieceId");

-- CreateIndex
CREATE INDEX "carousel_slides_carouselPostId_idx" ON "carousel_slides"("carouselPostId");

-- CreateIndex
CREATE UNIQUE INDEX "carousel_slides_carouselPostId_position_key" ON "carousel_slides"("carouselPostId", "position");

-- CreateIndex
CREATE UNIQUE INDEX "reels_contentPieceId_key" ON "reels"("contentPieceId");

-- CreateIndex
CREATE INDEX "media_assets_contentPieceId_idx" ON "media_assets"("contentPieceId");

-- CreateIndex
CREATE INDEX "media_assets_contentHash_idx" ON "media_assets"("contentHash");

-- CreateIndex
CREATE INDEX "audio_assets_reelId_idx" ON "audio_assets"("reelId");

-- CreateIndex
CREATE UNIQUE INDEX "captions_contentPieceId_platform_key" ON "captions"("contentPieceId", "platform");

-- CreateIndex
CREATE UNIQUE INDEX "hashtags_tag_key" ON "hashtags"("tag");

-- CreateIndex
CREATE INDEX "qa_results_contentPieceId_idx" ON "qa_results"("contentPieceId");

-- CreateIndex
CREATE INDEX "content_scores_contentPieceId_scoreType_idx" ON "content_scores"("contentPieceId", "scoreType");

-- CreateIndex
CREATE UNIQUE INDEX "publishing_jobs_idempotencyKey_key" ON "publishing_jobs"("idempotencyKey");

-- CreateIndex
CREATE INDEX "publishing_jobs_status_scheduledAt_idx" ON "publishing_jobs"("status", "scheduledAt");

-- CreateIndex
CREATE INDEX "publishing_jobs_contentPieceId_idx" ON "publishing_jobs"("contentPieceId");

-- CreateIndex
CREATE INDEX "publishing_jobs_socialAccountId_idx" ON "publishing_jobs"("socialAccountId");

-- CreateIndex
CREATE INDEX "publishing_attempts_publishingJobId_idx" ON "publishing_attempts"("publishingJobId");

-- CreateIndex
CREATE INDEX "analytics_records_socialAccountId_collectedAt_idx" ON "analytics_records"("socialAccountId", "collectedAt");

-- CreateIndex
CREATE INDEX "analytics_records_platformPostId_idx" ON "analytics_records"("platformPostId");

-- CreateIndex
CREATE INDEX "performance_snapshots_socialAccountId_capturedAt_idx" ON "performance_snapshots"("socialAccountId", "capturedAt");

-- CreateIndex
CREATE INDEX "learning_insights_organizationId_dimension_idx" ON "learning_insights"("organizationId", "dimension");

-- CreateIndex
CREATE UNIQUE INDEX "learning_insights_organizationId_dimension_key_windowEnd_key" ON "learning_insights"("organizationId", "dimension", "key", "windowEnd");

-- CreateIndex
CREATE INDEX "experiments_organizationId_status_idx" ON "experiments"("organizationId", "status");

-- CreateIndex
CREATE INDEX "system_memories_organizationId_memoryType_idx" ON "system_memories"("organizationId", "memoryType");

-- CreateIndex
CREATE UNIQUE INDEX "system_memories_organizationId_memoryType_key_key" ON "system_memories"("organizationId", "memoryType", "key");

-- CreateIndex
CREATE INDEX "prompts_key_isActive_idx" ON "prompts"("key", "isActive");

-- CreateIndex
CREATE UNIQUE INDEX "prompts_key_version_key" ON "prompts"("key", "version");

-- CreateIndex
CREATE INDEX "agent_runs_organizationId_agentName_startedAt_idx" ON "agent_runs"("organizationId", "agentName", "startedAt");

-- CreateIndex
CREATE INDEX "agent_runs_status_idx" ON "agent_runs"("status");

-- CreateIndex
CREATE INDEX "agent_errors_agentRunId_idx" ON "agent_errors"("agentRunId");

-- CreateIndex
CREATE INDEX "cost_entries_organizationId_createdAt_idx" ON "cost_entries"("organizationId", "createdAt");

-- CreateIndex
CREATE INDEX "cost_entries_contentPieceId_idx" ON "cost_entries"("contentPieceId");

-- CreateIndex
CREATE UNIQUE INDEX "automation_states_organizationId_key" ON "automation_states"("organizationId");

-- CreateIndex
CREATE INDEX "audit_logs_organizationId_createdAt_idx" ON "audit_logs"("organizationId", "createdAt");

-- CreateIndex
CREATE INDEX "audit_logs_action_idx" ON "audit_logs"("action");

-- AddForeignKey
ALTER TABLE "users" ADD CONSTRAINT "users_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "brands" ADD CONSTRAINT "brands_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "social_accounts" ADD CONSTRAINT "social_accounts_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "social_accounts" ADD CONSTRAINT "social_accounts_brandId_fkey" FOREIGN KEY ("brandId") REFERENCES "brands"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "platform_tokens" ADD CONSTRAINT "platform_tokens_socialAccountId_fkey" FOREIGN KEY ("socialAccountId") REFERENCES "social_accounts"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "topics" ADD CONSTRAINT "topics_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "topics" ADD CONSTRAINT "topics_brandId_fkey" FOREIGN KEY ("brandId") REFERENCES "brands"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sources" ADD CONSTRAINT "sources_topicId_fkey" FOREIGN KEY ("topicId") REFERENCES "topics"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claims" ADD CONSTRAINT "claims_topicId_fkey" FOREIGN KEY ("topicId") REFERENCES "topics"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claims" ADD CONSTRAINT "claims_sourceId_fkey" FOREIGN KEY ("sourceId") REFERENCES "sources"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "research_reports" ADD CONSTRAINT "research_reports_topicId_fkey" FOREIGN KEY ("topicId") REFERENCES "topics"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_ideas" ADD CONSTRAINT "content_ideas_topicId_fkey" FOREIGN KEY ("topicId") REFERENCES "topics"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_pieces" ADD CONSTRAINT "content_pieces_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_pieces" ADD CONSTRAINT "content_pieces_brandId_fkey" FOREIGN KEY ("brandId") REFERENCES "brands"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_pieces" ADD CONSTRAINT "content_pieces_topicId_fkey" FOREIGN KEY ("topicId") REFERENCES "topics"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_pieces" ADD CONSTRAINT "content_pieces_contentIdeaId_fkey" FOREIGN KEY ("contentIdeaId") REFERENCES "content_ideas"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_status_changes" ADD CONSTRAINT "content_status_changes_contentPieceId_fkey" FOREIGN KEY ("contentPieceId") REFERENCES "content_pieces"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "carousel_posts" ADD CONSTRAINT "carousel_posts_contentPieceId_fkey" FOREIGN KEY ("contentPieceId") REFERENCES "content_pieces"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "carousel_slides" ADD CONSTRAINT "carousel_slides_carouselPostId_fkey" FOREIGN KEY ("carouselPostId") REFERENCES "carousel_posts"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "carousel_slides" ADD CONSTRAINT "carousel_slides_mediaAssetId_fkey" FOREIGN KEY ("mediaAssetId") REFERENCES "media_assets"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "reels" ADD CONSTRAINT "reels_contentPieceId_fkey" FOREIGN KEY ("contentPieceId") REFERENCES "content_pieces"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "media_assets" ADD CONSTRAINT "media_assets_contentPieceId_fkey" FOREIGN KEY ("contentPieceId") REFERENCES "content_pieces"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "audio_assets" ADD CONSTRAINT "audio_assets_reelId_fkey" FOREIGN KEY ("reelId") REFERENCES "reels"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "captions" ADD CONSTRAINT "captions_contentPieceId_fkey" FOREIGN KEY ("contentPieceId") REFERENCES "content_pieces"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "qa_results" ADD CONSTRAINT "qa_results_contentPieceId_fkey" FOREIGN KEY ("contentPieceId") REFERENCES "content_pieces"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "content_scores" ADD CONSTRAINT "content_scores_contentPieceId_fkey" FOREIGN KEY ("contentPieceId") REFERENCES "content_pieces"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "publishing_jobs" ADD CONSTRAINT "publishing_jobs_contentPieceId_fkey" FOREIGN KEY ("contentPieceId") REFERENCES "content_pieces"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "publishing_jobs" ADD CONSTRAINT "publishing_jobs_socialAccountId_fkey" FOREIGN KEY ("socialAccountId") REFERENCES "social_accounts"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "publishing_attempts" ADD CONSTRAINT "publishing_attempts_publishingJobId_fkey" FOREIGN KEY ("publishingJobId") REFERENCES "publishing_jobs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "analytics_records" ADD CONSTRAINT "analytics_records_socialAccountId_fkey" FOREIGN KEY ("socialAccountId") REFERENCES "social_accounts"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "analytics_records" ADD CONSTRAINT "analytics_records_publishingJobId_fkey" FOREIGN KEY ("publishingJobId") REFERENCES "publishing_jobs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "performance_snapshots" ADD CONSTRAINT "performance_snapshots_socialAccountId_fkey" FOREIGN KEY ("socialAccountId") REFERENCES "social_accounts"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "experiments" ADD CONSTRAINT "experiments_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "system_memories" ADD CONSTRAINT "system_memories_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "agent_errors" ADD CONSTRAINT "agent_errors_agentRunId_fkey" FOREIGN KEY ("agentRunId") REFERENCES "agent_runs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "cost_entries" ADD CONSTRAINT "cost_entries_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "cost_entries" ADD CONSTRAINT "cost_entries_topicId_fkey" FOREIGN KEY ("topicId") REFERENCES "topics"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "cost_entries" ADD CONSTRAINT "cost_entries_contentPieceId_fkey" FOREIGN KEY ("contentPieceId") REFERENCES "content_pieces"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "automation_states" ADD CONSTRAINT "automation_states_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "audit_logs" ADD CONSTRAINT "audit_logs_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE CASCADE ON UPDATE CASCADE;
