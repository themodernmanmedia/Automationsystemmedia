/**
 * S3-compatible object storage.
 *
 * This is not an optional convenience. Meta FETCHES media from a URL rather
 * than accepting uploaded bytes, so Instagram publishing is impossible without
 * publicly-resolvable storage. Signing is implemented directly (AWS SigV4) to
 * avoid pulling the AWS SDK in for one operation.
 *
 * Works with S3, Cloudflare R2, Backblaze B2, and MinIO.
 */
import { createHash, createHmac } from 'node:crypto';
import { AppError, ProviderNotConfiguredError, withRetry } from '@mmos/core';
import type { StorageProvider, StoredObject } from '../types.js';

export interface S3Config {
  endpoint?: string;
  region: string;
  bucket?: string;
  accessKeyId?: string;
  secretAccessKey?: string;
  publicBaseUrl?: string;
}

export class S3StorageProvider implements StorageProvider {
  readonly name = 's3';
  readonly #endpoint: string;
  readonly #region: string;
  readonly #bucket: string;
  readonly #accessKeyId: string;
  readonly #secretAccessKey: string;
  readonly #publicBaseUrl: string;

  constructor(config: S3Config) {
    const missing: string[] = [];
    if (!config.bucket) missing.push('S3_BUCKET');
    if (!config.accessKeyId) missing.push('S3_ACCESS_KEY_ID');
    if (!config.secretAccessKey) missing.push('S3_SECRET_ACCESS_KEY');
    if (!config.publicBaseUrl) missing.push('S3_PUBLIC_BASE_URL');
    if (missing.length > 0) {
      throw new ProviderNotConfiguredError(
        'S3 storage (required for Instagram publishing — Meta fetches media from a public URL)',
        missing,
      );
    }
    this.#bucket = config.bucket as string;
    this.#accessKeyId = config.accessKeyId as string;
    this.#secretAccessKey = config.secretAccessKey as string;
    this.#publicBaseUrl = (config.publicBaseUrl as string).replace(/\/$/, '');
    this.#region = config.region;
    this.#endpoint = (config.endpoint ?? `https://s3.${config.region}.amazonaws.com`).replace(/\/$/, '');
  }

  getPublicUrl(key: string): string {
    return `${this.#publicBaseUrl}/${key.replace(/^\//, '')}`;
  }

  async put(key: string, data: Buffer, mimeType: string): Promise<StoredObject> {
    const normalizedKey = key.replace(/^\//, '');
    await withRetry(
      async () => {
        const res = await this.#signedFetch('PUT', normalizedKey, data, mimeType);
        if (!res.ok) {
          const text = await res.text();
          throw new AppError(`S3 PUT failed with HTTP ${res.status}: ${text.slice(0, 300)}`, {
            code: 'MEDIA_ERROR',
            retryable: res.status >= 500,
          });
        }
      },
      { maxAttempts: 3, baseDelayMs: 1000 },
    );

    return {
      key: normalizedKey,
      publicUrl: this.getPublicUrl(normalizedKey),
      sizeBytes: data.byteLength,
      mimeType,
    };
  }

  async delete(key: string): Promise<void> {
    const res = await this.#signedFetch('DELETE', key.replace(/^\//, ''));
    if (!res.ok && res.status !== 404) {
      throw new AppError(`S3 DELETE failed with HTTP ${res.status}`, { code: 'MEDIA_ERROR' });
    }
  }

  async #signedFetch(method: string, key: string, body?: Buffer, contentType?: string): Promise<Response> {
    const url = new URL(`${this.#endpoint}/${this.#bucket}/${key}`);
    const now = new Date();
    const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, '');
    const dateStamp = amzDate.slice(0, 8);
    const payloadHash = createHash('sha256')
      .update(body ?? Buffer.alloc(0))
      .digest('hex');

    const headers: Record<string, string> = {
      host: url.host,
      'x-amz-content-sha256': payloadHash,
      'x-amz-date': amzDate,
    };
    if (contentType) headers['content-type'] = contentType;

    const signedHeaderNames = Object.keys(headers).sort();
    const canonicalHeaders = signedHeaderNames.map((h) => `${h}:${headers[h]}\n`).join('');
    const signedHeaders = signedHeaderNames.join(';');

    const canonicalRequest = [
      method,
      url.pathname,
      '',
      canonicalHeaders,
      signedHeaders,
      payloadHash,
    ].join('\n');

    const scope = `${dateStamp}/${this.#region}/s3/aws4_request`;
    const stringToSign = [
      'AWS4-HMAC-SHA256',
      amzDate,
      scope,
      createHash('sha256').update(canonicalRequest).digest('hex'),
    ].join('\n');

    const signingKey = ['aws4_request', 's3', this.#region, dateStamp].reduceRight(
      (key, part) => createHmac('sha256', key).update(part).digest(),
      Buffer.from(`AWS4${this.#secretAccessKey}`) as Buffer,
    );
    const signature = createHmac('sha256', signingKey).update(stringToSign).digest('hex');

    headers['authorization'] =
      `AWS4-HMAC-SHA256 Credential=${this.#accessKeyId}/${scope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

    return fetch(url, {
      method,
      headers,
      ...(body ? { body: new Uint8Array(body) } : {}),
    });
  }
}
