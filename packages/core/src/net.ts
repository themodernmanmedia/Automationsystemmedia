/**
 * Outbound fetch guard for attacker-influenced URLs.
 *
 * The research pipeline follows links it did not choose: an RSS `<link>` is
 * written by whoever controls the feed, and it reaches `fetch` from inside the
 * deployment network. Without a check that is a server-side request forgery
 * primitive — the worker will happily retrieve a cloud metadata endpoint or an
 * unauthenticated admin port and, because the body is stored as source text,
 * hand it back through the API.
 *
 * The rule is therefore an allowlist of shapes rather than a denylist of known
 * bad hosts: http(s) only, no embedded credentials, and every address the
 * hostname resolves to must be publicly routable. Redirects are followed
 * manually so each hop is re-checked; a 302 to `169.254.169.254` is the obvious
 * bypass of a check applied only to the first URL.
 *
 * Known residual risk, stated plainly rather than papered over: validation
 * resolves the hostname and then lets the platform connect, so a DNS entry that
 * changes between those two moments (rebinding) is not caught. Closing that
 * needs connection-level address pinning, which the platform fetch does not
 * expose. The window is narrow and the guard still removes the direct,
 * scriptable path, but it is not a complete mitigation.
 */
import { lookup } from 'node:dns/promises';
import { isIP } from 'node:net';
import { AppError, ErrorCode } from './errors.js';

export class BlockedUrlError extends AppError {
  constructor(url: string, reason: string) {
    super(`Refusing to fetch ${url}: ${reason}`, {
      code: ErrorCode.VALIDATION_ERROR,
      httpStatus: 400,
      retryable: false,
      context: { reason },
    });
  }
}

function ipv4ToInt(ip: string): number | null {
  const parts = ip.split('.');
  if (parts.length !== 4) return null;
  let n = 0;
  for (const part of parts) {
    const octet = Number(part);
    if (!Number.isInteger(octet) || octet < 0 || octet > 255) return null;
    n = n * 256 + octet;
  }
  return n;
}

/** CIDR blocks that are not publicly routable, or route somewhere we must not reach. */
const BLOCKED_V4: ReadonlyArray<readonly [string, number, string]> = [
  ['0.0.0.0', 8, 'unspecified'],
  ['10.0.0.0', 8, 'private'],
  ['100.64.0.0', 10, 'carrier-grade NAT'],
  ['127.0.0.0', 8, 'loopback'],
  ['169.254.0.0', 16, 'link-local / cloud metadata'],
  ['172.16.0.0', 12, 'private'],
  ['192.0.0.0', 24, 'IETF protocol assignments'],
  ['192.0.2.0', 24, 'documentation'],
  ['192.168.0.0', 16, 'private'],
  ['198.18.0.0', 15, 'benchmarking'],
  ['198.51.100.0', 24, 'documentation'],
  ['203.0.113.0', 24, 'documentation'],
  ['224.0.0.0', 4, 'multicast'],
  ['240.0.0.0', 4, 'reserved'],
];

function blockedReasonV4(ip: string): string | null {
  const value = ipv4ToInt(ip);
  if (value === null) return 'unparseable IPv4 address';
  for (const [base, bits, reason] of BLOCKED_V4) {
    const baseValue = ipv4ToInt(base);
    if (baseValue === null) continue;
    const mask = bits === 0 ? 0 : (-1 << (32 - bits)) >>> 0;
    if ((value & mask) >>> 0 === (baseValue & mask) >>> 0) return reason;
  }
  return null;
}

function blockedReasonV6(ip: string): string | null {
  const lower = ip.toLowerCase().split('%')[0] ?? '';

  // IPv4 reachable through a v6 wrapper: mapped (::ffff:a.b.c.d), NAT64
  // (64:ff9b::a.b.c.d) and 6to4 (2002:aabb:ccdd::) all carry a v4 destination,
  // so the v4 rules are what actually decide.
  const embeddedDotted = lower.match(/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/);
  if (embeddedDotted?.[1] && (lower.startsWith('::ffff:') || lower.startsWith('64:ff9b:'))) {
    return blockedReasonV4(embeddedDotted[1]);
  }
  if (lower.startsWith('2002:')) {
    const groups = lower.split(':');
    const hi = Number.parseInt(groups[1] ?? '', 16);
    const lo = Number.parseInt(groups[2] ?? '', 16);
    if (Number.isInteger(hi) && Number.isInteger(lo)) {
      const dotted = `${hi >> 8}.${hi & 0xff}.${lo >> 8}.${lo & 0xff}`;
      return blockedReasonV4(dotted);
    }
  }

  if (lower === '::' || lower === '::0') return 'unspecified';
  if (lower === '::1') return 'loopback';
  const firstGroup = Number.parseInt(lower.split(':')[0] || '0', 16);
  if ((firstGroup & 0xfe00) === 0xfc00) return 'unique local';
  if ((firstGroup & 0xffc0) === 0xfe80) return 'link-local';
  if ((firstGroup & 0xff00) === 0xff00) return 'multicast';
  return null;
}

/** Why this literal address must not be fetched, or null if it is routable. */
export function blockedAddressReason(ip: string): string | null {
  const version = isIP(ip);
  if (version === 4) return blockedReasonV4(ip);
  if (version === 6) return blockedReasonV6(ip);
  return 'not an IP address';
}

export interface UrlGuardOptions {
  /** Overrides DNS resolution. Tests use it; production never sets it. */
  resolve?: (hostname: string) => Promise<string[]>;
}

async function resolveHost(hostname: string, options: UrlGuardOptions): Promise<string[]> {
  if (options.resolve) return options.resolve(hostname);
  const records = await lookup(hostname, { all: true, verbatim: true });
  return records.map((r) => r.address);
}

/**
 * Throws unless `raw` is a public http(s) URL. Returns the parsed URL so the
 * caller fetches exactly what was checked rather than re-parsing.
 */
export async function assertPublicUrl(raw: string, options: UrlGuardOptions = {}): Promise<URL> {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new BlockedUrlError(raw, 'not a valid absolute URL');
  }

  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new BlockedUrlError(raw, `scheme ${url.protocol} is not allowed`);
  }
  // Credentials in a URL are never legitimate here and would be sent onward.
  if (url.username || url.password) {
    throw new BlockedUrlError(raw, 'URL contains embedded credentials');
  }

  const hostname = url.hostname.replace(/^\[|\]$/g, '');
  if (!hostname) throw new BlockedUrlError(raw, 'URL has no host');

  // A literal address skips DNS entirely and is decided on its own.
  if (isIP(hostname)) {
    const reason = blockedAddressReason(hostname);
    if (reason) throw new BlockedUrlError(raw, `address is ${reason}`);
    return url;
  }

  let addresses: string[];
  try {
    addresses = await resolveHost(hostname, options);
  } catch {
    throw new BlockedUrlError(raw, `host ${hostname} could not be resolved`);
  }
  if (addresses.length === 0) throw new BlockedUrlError(raw, `host ${hostname} resolved to no addresses`);

  // Every address must be safe. One public answer alongside a private one is a
  // classic bypass, since which address the connection uses is not ours to pick.
  for (const address of addresses) {
    const reason = blockedAddressReason(address);
    if (reason) throw new BlockedUrlError(raw, `host ${hostname} resolves to a ${reason} address`);
  }

  return url;
}

export interface SafeFetchOptions extends UrlGuardOptions {
  headers?: Record<string, string>;
  timeoutMs?: number;
  /** Redirect hops to follow, each re-validated. Default 3. */
  maxRedirects?: number;
}

/**
 * `fetch` for URLs the system did not choose. Validates before connecting and
 * again on every redirect hop, and never follows a redirect automatically.
 */
export async function safeFetch(raw: string, options: SafeFetchOptions = {}): Promise<Response> {
  const maxRedirects = options.maxRedirects ?? 3;
  let target = raw;

  for (let hop = 0; hop <= maxRedirects; hop++) {
    const url = await assertPublicUrl(target, options);
    const res = await fetch(url, {
      headers: options.headers ?? {},
      redirect: 'manual',
      signal: AbortSignal.timeout(options.timeoutMs ?? 15_000),
    });

    if (res.status < 300 || res.status > 399) return res;

    const location = res.headers.get('location');
    if (!location) return res;
    // Cancel the body of the hop we are abandoning so the socket is released.
    await res.body?.cancel().catch(() => undefined);
    target = new URL(location, url).toString();
  }

  throw new BlockedUrlError(raw, `exceeded ${maxRedirects} redirects`);
}
