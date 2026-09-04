import { describe, expect, it } from 'vitest';
import { redactUrl } from './http.js';

describe('redactUrl', () => {
  it('redacts fb_exchange_token, which carries a live access token', () => {
    // The regression this test exists for: the previous exact-name list covered
    // client_secret on this very request but not fb_exchange_token, so a failed
    // long-lived-token exchange logged a working token in cleartext.
    const url = redactUrl(
      'https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=123&client_secret=SECRET&fb_exchange_token=EAAG_LIVE_TOKEN',
    );
    expect(url).not.toContain('EAAG_LIVE_TOKEN');
    expect(url).not.toContain('SECRET');
    expect(url).toContain('fb_exchange_token=%5BREDACTED%5D');
  });

  it.each([
    'access_token',
    'refresh_token',
    'client_secret',
    'code',
    'api_key',
    'apiKey',
    'appsecret_proof',
    'page_access_token',
  ])('redacts %s', (param) => {
    const url = redactUrl(`https://graph.facebook.com/v21.0/me?${param}=SENSITIVE_VALUE`);
    expect(url).not.toContain('SENSITIVE_VALUE');
  });

  it('keeps parameters that are useful for debugging', () => {
    const url = redactUrl('https://graph.facebook.com/v21.0/me/media?fields=id,status_code&limit=25');
    expect(url).toMatch(/fields=id(,|%2C)status_code/);
    expect(url).toContain('limit=25');
  });

  it('redacts credentials embedded in the authority', () => {
    expect(redactUrl('https://user:hunter2@graph.facebook.com/v21.0/me')).not.toContain('hunter2');
  });

  it('returns a URL it cannot parse unchanged rather than throwing', () => {
    expect(redactUrl('not a url')).toBe('not a url');
  });
});
