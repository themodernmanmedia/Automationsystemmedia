/**
 * Token-bucket rate limiter for OUTBOUND platform calls.
 *
 * The point is not to protect us — it is to protect the brand's social accounts.
 * Tripping a platform's limits repeatedly is how automated tools get accounts
 * restricted, so we stay under the documented ceilings by construction.
 */
export interface TokenBucketOptions {
  capacity: number;
  refillPerSecond: number;
  now?: () => number;
}

export class TokenBucket {
  #tokens: number;
  #lastRefill: number;
  readonly #capacity: number;
  readonly #refillPerSecond: number;
  readonly #now: () => number;

  constructor(opts: TokenBucketOptions) {
    this.#capacity = opts.capacity;
    this.#refillPerSecond = opts.refillPerSecond;
    this.#now = opts.now ?? Date.now;
    this.#tokens = opts.capacity;
    this.#lastRefill = this.#now();
  }

  #refill(): void {
    const now = this.#now();
    const elapsedSec = (now - this.#lastRefill) / 1000;
    if (elapsedSec <= 0) return;
    this.#tokens = Math.min(this.#capacity, this.#tokens + elapsedSec * this.#refillPerSecond);
    this.#lastRefill = now;
  }

  tryConsume(count = 1): boolean {
    this.#refill();
    if (this.#tokens < count) return false;
    this.#tokens -= count;
    return true;
  }

  /** Milliseconds until `count` tokens are available; 0 if available now. */
  msUntilAvailable(count = 1): number {
    this.#refill();
    if (this.#tokens >= count) return 0;
    return Math.ceil(((count - this.#tokens) / this.#refillPerSecond) * 1000);
  }

  get available(): number {
    this.#refill();
    return Math.floor(this.#tokens);
  }
}
