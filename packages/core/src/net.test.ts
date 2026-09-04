import { describe, expect, it } from 'vitest';
import { assertPublicUrl, blockedAddressReason, BlockedUrlError, safeFetch } from './net.js';

const resolveTo = (...addresses: string[]) => async () => addresses;

describe('blockedAddressReason', () => {
  it.each([
    ['169.254.169.254', 'link-local / cloud metadata'],
    ['127.0.0.1', 'loopback'],
    ['10.4.5.6', 'private'],
    ['172.16.0.1', 'private'],
    ['172.31.255.254', 'private'],
    ['192.168.1.1', 'private'],
    ['100.64.0.1', 'carrier-grade NAT'],
    ['0.0.0.0', 'unspecified'],
    ['224.0.0.1', 'multicast'],
  ])('blocks %s', (ip, reason) => {
    expect(blockedAddressReason(ip)).toBe(reason);
  });

  it.each(['8.8.8.8', '1.1.1.1', '172.32.0.1', '172.15.255.255', '93.184.216.34'])(
    'allows public address %s',
    (ip) => {
      expect(blockedAddressReason(ip)).toBeNull();
    },
  );

  it.each([
    ['::1', 'loopback'],
    ['fd00::1', 'unique local'],
    ['fe80::1', 'link-local'],
    ['ff02::1', 'multicast'],
  ])('blocks IPv6 %s', (ip, reason) => {
    expect(blockedAddressReason(ip)).toBe(reason);
  });

  it('sees through IPv4-mapped and NAT64 wrappers to the real destination', () => {
    expect(blockedAddressReason('::ffff:169.254.169.254')).toBe('link-local / cloud metadata');
    expect(blockedAddressReason('64:ff9b::127.0.0.1')).toBe('loopback');
    expect(blockedAddressReason('::ffff:8.8.8.8')).toBeNull();
  });

  it('sees through a 6to4 wrapper', () => {
    // 2002:a9fe:a9fe:: embeds 169.254.169.254
    expect(blockedAddressReason('2002:a9fe:a9fe::1')).toBe('link-local / cloud metadata');
  });

  it('allows a genuine public IPv6 address', () => {
    expect(blockedAddressReason('2606:4700:4700::1111')).toBeNull();
  });
});

describe('assertPublicUrl', () => {
  it('accepts an ordinary article URL', async () => {
    const url = await assertPublicUrl('https://example.com/post', { resolve: resolveTo('93.184.216.34') });
    expect(url.hostname).toBe('example.com');
  });

  it('rejects a non-web scheme', async () => {
    await expect(assertPublicUrl('file:///etc/passwd')).rejects.toBeInstanceOf(BlockedUrlError);
    await expect(assertPublicUrl('gopher://example.com/')).rejects.toThrow(/scheme/);
  });

  it('rejects embedded credentials', async () => {
    await expect(assertPublicUrl('https://user:pw@example.com/')).rejects.toThrow(/credentials/);
  });

  it('rejects the cloud metadata address given as a literal', async () => {
    await expect(assertPublicUrl('http://169.254.169.254/latest/meta-data/')).rejects.toThrow(
      /link-local/,
    );
  });

  it('rejects a hostname that resolves to a private address', async () => {
    await expect(
      assertPublicUrl('https://internal.example.com/', { resolve: resolveTo('10.0.0.5') }),
    ).rejects.toThrow(/private/);
  });

  it('rejects a hostname that resolves to one public and one private address', async () => {
    // Answering with a public address alongside a private one is the standard
    // bypass, since the connection picks the address, not us.
    await expect(
      assertPublicUrl('https://mixed.example.com/', { resolve: resolveTo('8.8.8.8', '127.0.0.1') }),
    ).rejects.toThrow(/loopback/);
  });

  it('rejects a hostname that does not resolve', async () => {
    await expect(
      assertPublicUrl('https://nx.example.com/', {
        resolve: async () => {
          throw new Error('ENOTFOUND');
        },
      }),
    ).rejects.toThrow(/could not be resolved/);
  });

  it('rejects a relative URL', async () => {
    await expect(assertPublicUrl('/latest/meta-data/')).rejects.toThrow(/absolute URL/);
  });
});

describe('safeFetch redirect handling', () => {
  const originalFetch = globalThis.fetch;

  it('re-validates every redirect hop', async () => {
    const seen: string[] = [];
    globalThis.fetch = (async (input: URL | RequestInfo) => {
      const target = String(input);
      seen.push(target);
      if (target.startsWith('https://feed.example.com')) {
        return new Response(null, {
          status: 302,
          headers: { location: 'http://169.254.169.254/latest/meta-data/' },
        });
      }
      return new Response('should never be reached', { status: 200 });
    }) as typeof fetch;

    try {
      await expect(
        safeFetch('https://feed.example.com/a', { resolve: resolveTo('93.184.216.34') }),
      ).rejects.toThrow(/link-local/);
      // The metadata address was never actually requested.
      expect(seen).toEqual(['https://feed.example.com/a']);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('follows a redirect that stays public', async () => {
    globalThis.fetch = (async (input: URL | RequestInfo) => {
      const target = String(input);
      if (target.endsWith('/a')) {
        return new Response(null, { status: 301, headers: { location: 'https://example.com/b' } });
      }
      return new Response('body', { status: 200 });
    }) as typeof fetch;

    try {
      const res = await safeFetch('https://example.com/a', { resolve: resolveTo('93.184.216.34') });
      expect(await res.text()).toBe('body');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('stops after the redirect limit rather than looping', async () => {
    globalThis.fetch = (async () =>
      new Response(null, {
        status: 302,
        headers: { location: 'https://example.com/loop' },
      })) as typeof fetch;

    try {
      await expect(
        safeFetch('https://example.com/loop', { resolve: resolveTo('93.184.216.34'), maxRedirects: 2 }),
      ).rejects.toThrow(/exceeded 2 redirects/);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
