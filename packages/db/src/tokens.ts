/**
 * Platform credential storage.
 *
 * Every read and write of token material goes through here, so encryption is
 * structurally impossible to forget — no other module touches `accessTokenEnc`.
 */
import { Encryptor } from '@mmos/core';
import { prisma } from './client.js';

export interface DecryptedToken {
  accessToken: string;
  refreshToken: string | null;
  expiresAt: Date | null;
  refreshExpiresAt: Date | null;
  scopes: string[];
}

export interface StoreTokenInput {
  socialAccountId: string;
  accessToken: string;
  refreshToken?: string | null;
  expiresAt?: Date | null;
  refreshExpiresAt?: Date | null;
  scopes?: string[];
  tokenType?: string;
}

export class TokenStore {
  readonly #enc: Encryptor;

  constructor(encryptionKey: string) {
    this.#enc = new Encryptor(encryptionKey);
  }

  async store(input: StoreTokenInput): Promise<void> {
    const data = {
      accessTokenEnc: this.#enc.encrypt(input.accessToken),
      refreshTokenEnc: this.#enc.encryptOptional(input.refreshToken),
      expiresAt: input.expiresAt ?? null,
      refreshExpiresAt: input.refreshExpiresAt ?? null,
      scopes: input.scopes ?? [],
      tokenType: input.tokenType ?? 'bearer',
      lastRefreshedAt: new Date(),
      refreshFailures: 0,
    };
    await prisma.platformToken.upsert({
      where: { socialAccountId: input.socialAccountId },
      create: { socialAccountId: input.socialAccountId, ...data },
      update: data,
    });
  }

  async get(socialAccountId: string): Promise<DecryptedToken | null> {
    const row = await prisma.platformToken.findUnique({ where: { socialAccountId } });
    if (!row) return null;
    return {
      accessToken: this.#enc.decrypt(row.accessTokenEnc),
      refreshToken: this.#enc.decryptOptional(row.refreshTokenEnc),
      expiresAt: row.expiresAt,
      refreshExpiresAt: row.refreshExpiresAt,
      scopes: row.scopes,
    };
  }

  async recordRefreshFailure(socialAccountId: string): Promise<number> {
    const row = await prisma.platformToken.update({
      where: { socialAccountId },
      data: { refreshFailures: { increment: 1 } },
      select: { refreshFailures: true },
    });
    return row.refreshFailures;
  }

  async delete(socialAccountId: string): Promise<void> {
    await prisma.platformToken.deleteMany({ where: { socialAccountId } });
  }

  /**
   * Accounts whose token expires inside the window. The refresh worker uses a
   * lead time rather than waiting for expiry, because a token that expires
   * between scheduling and publishing costs a missed post.
   */
  async findExpiring(withinMs: number): Promise<string[]> {
    const threshold = new Date(Date.now() + withinMs);
    const rows = await prisma.platformToken.findMany({
      where: { expiresAt: { not: null, lte: threshold } },
      select: { socialAccountId: true },
    });
    return rows.map((r) => r.socialAccountId);
  }
}
