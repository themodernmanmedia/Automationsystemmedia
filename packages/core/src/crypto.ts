/**
 * Encryption for platform credentials at rest.
 *
 * AES-256-GCM. Ciphertext is stored as `v1:<iv-b64>:<tag-b64>:<data-b64>` — the
 * version prefix exists so a future key rotation or algorithm change can decrypt
 * old rows while writing new ones, instead of requiring a flag-day migration.
 */
import {
  createCipheriv,
  createDecipheriv,
  randomBytes,
  scryptSync,
  timingSafeEqual,
  createHmac,
} from 'node:crypto';
import { ValidationError } from './errors.js';

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 12; // 96-bit nonce, the GCM-recommended size
const KEY_LENGTH = 32;
const VERSION = 'v1';

export class Encryptor {
  readonly #key: Buffer;

  constructor(base64Key: string) {
    let key: Buffer;
    try {
      key = Buffer.from(base64Key, 'base64');
    } catch {
      throw new ValidationError('ENCRYPTION_KEY is not valid base64');
    }
    if (key.length !== KEY_LENGTH) {
      throw new ValidationError(
        `ENCRYPTION_KEY must decode to exactly ${KEY_LENGTH} bytes (got ${key.length}). Generate one with: openssl rand -base64 32`,
      );
    }
    this.#key = key;
  }

  encrypt(plaintext: string): string {
    const iv = randomBytes(IV_LENGTH);
    const cipher = createCipheriv(ALGORITHM, this.#key, iv);
    const data = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()]);
    const tag = cipher.getAuthTag();
    return [VERSION, iv.toString('base64'), tag.toString('base64'), data.toString('base64')].join(':');
  }

  decrypt(ciphertext: string): string {
    const parts = ciphertext.split(':');
    if (parts.length !== 4) throw new ValidationError('Malformed ciphertext envelope');
    const [version, ivB64, tagB64, dataB64] = parts as [string, string, string, string];
    if (version !== VERSION) throw new ValidationError(`Unsupported ciphertext version: ${version}`);

    const decipher = createDecipheriv(ALGORITHM, this.#key, Buffer.from(ivB64, 'base64'));
    decipher.setAuthTag(Buffer.from(tagB64, 'base64'));
    try {
      return Buffer.concat([
        decipher.update(Buffer.from(dataB64, 'base64')),
        decipher.final(),
      ]).toString('utf8');
    } catch {
      // GCM auth failure: wrong key or tampered ciphertext. Deliberately vague.
      throw new ValidationError('Failed to decrypt: authentication check failed');
    }
  }

  /** Encrypt only when a value is present, so optional refresh tokens stay optional. */
  encryptOptional(plaintext: string | null | undefined): string | null {
    return plaintext == null || plaintext === '' ? null : this.encrypt(plaintext);
  }

  decryptOptional(ciphertext: string | null | undefined): string | null {
    return ciphertext == null || ciphertext === '' ? null : this.decrypt(ciphertext);
  }
}

/* ------------------------------------------------------------------ */
/* Password hashing — scrypt with a per-user salt                      */
/* ------------------------------------------------------------------ */

const SCRYPT_N = 16384;
const SCRYPT_KEYLEN = 64;

export function hashPassword(password: string): string {
  const salt = randomBytes(16);
  const derived = scryptSync(password, salt, SCRYPT_KEYLEN, { N: SCRYPT_N });
  return `scrypt$${SCRYPT_N}$${salt.toString('base64')}$${derived.toString('base64')}`;
}

export function verifyPassword(password: string, stored: string): boolean {
  const parts = stored.split('$');
  if (parts.length !== 4 || parts[0] !== 'scrypt') return false;
  const n = Number(parts[1]);
  const salt = Buffer.from(parts[2] as string, 'base64');
  const expected = Buffer.from(parts[3] as string, 'base64');
  const actual = scryptSync(password, salt, expected.length, { N: n });
  // Length check first: timingSafeEqual throws on a length mismatch.
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}

/* ------------------------------------------------------------------ */
/* Signed values — used for the OAuth `state` parameter                */
/* ------------------------------------------------------------------ */

/**
 * OAuth `state` is the CSRF defense for the callback, so it must be unforgeable
 * and time-bounded. We sign a payload rather than storing a random value, so a
 * callback can be validated without a round trip.
 *
 * It is deliberately NOT single-use: there is no nonce store, so a signed state
 * can be replayed until it expires. That is acceptable only because the
 * provider `code` accompanying it is itself single-use and short-lived, so a
 * replayed state cannot complete a second exchange. Making state single-use
 * would require server-side storage and is the change to make if that
 * assumption ever stops holding.
 */
export function signValue(value: string, secret: string): string {
  const mac = createHmac('sha256', secret).update(value).digest('base64url');
  return `${Buffer.from(value, 'utf8').toString('base64url')}.${mac}`;
}

export function verifySignedValue(signed: string, secret: string): string | null {
  const dot = signed.lastIndexOf('.');
  if (dot <= 0) return null;
  const payloadB64 = signed.slice(0, dot);
  const mac = signed.slice(dot + 1);
  const value = Buffer.from(payloadB64, 'base64url').toString('utf8');
  const expected = createHmac('sha256', secret).update(value).digest('base64url');
  const a = Buffer.from(mac);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  return value;
}

export function randomToken(bytes = 32): string {
  return randomBytes(bytes).toString('base64url');
}

/** Stable fingerprint for dedupe/caching. Not a security primitive. */
export function fingerprint(input: string): string {
  return createHmac('sha256', 'mmos-fingerprint').update(input).digest('hex').slice(0, 32);
}
