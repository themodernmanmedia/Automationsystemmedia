import { describe, expect, it } from 'vitest';
import { stdSerializers } from 'pino';
import { Writable } from 'node:stream';
import { createLogger, errorSerializer, scrubSecrets } from './logger.js';
import { AppError } from './errors.js';

describe('scrubSecrets', () => {
  it('redacts a token carried in a query string', () => {
    const out = scrubSecrets(
      'https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&fb_exchange_token=EAAG_LIVE_TOKEN',
    );
    expect(out).not.toContain('EAAG_LIVE_TOKEN');
    expect(out).toContain('fb_exchange_token=[REDACTED]');
  });

  it('redacts URL userinfo', () => {
    expect(scrubSecrets('postgres://admin:hunter2@db.internal:5432/app')).toBe(
      'postgres://[REDACTED]@db.internal:5432/app',
    );
  });

  it('leaves ordinary text alone', () => {
    const text = 'published to instagram in 412ms with 3 sources';
    expect(scrubSecrets(text)).toBe(text);
  });
});

describe('error serializer', () => {
  it('scrubs a live token that reached the log through an error context', () => {
    // This is the exact shape the platform HTTP layer produces: the failing
    // request URL attached as error context, which pino copies because
    // `context` is an own enumerable property — `readonly` is compile-time only.
    const err = new AppError('token refresh failed', {
      context: {
        url: 'https://graph.facebook.com/v21.0/oauth/access_token?client_secret=%5BREDACTED%5D&fb_exchange_token=EAAG_LIVE_TOKEN',
        status: 500,
      },
    });

    expect(JSON.stringify(stdSerializers.err(err))).toContain('EAAG_LIVE_TOKEN');
    expect(JSON.stringify(errorSerializer(err))).not.toContain('EAAG_LIVE_TOKEN');
  });

  it('emits nothing sensitive through a configured logger', () => {
    let output = '';
    const sink = new Writable({
      write(chunk, _enc, cb) {
        output += String(chunk);
        cb();
      },
    });
    const log = createLogger({ level: 'error', destination: sink });
    log.error(
      { err: new AppError('boom', { context: { url: 'https://api.example.com/x?access_token=SECRET_ABC' } }) },
      'token refresh failed',
    );

    expect(output).not.toContain('SECRET_ABC');
    expect(output).toContain('[REDACTED]');
  });
});
