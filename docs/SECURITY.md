# Security

## Threat model
The high-value assets are (a) platform OAuth tokens, which grant publishing rights to the
brand's audience, and (b) the publishing path itself, since an attacker who reaches it can
post as the brand. Everything below prioritizes those two.

## Secrets and tokens
- **Encrypted at rest.** Platform access/refresh tokens are sealed with AES-256-GCM
  (`packages/core/src/crypto.ts`) using `ENCRYPTION_KEY` (32 bytes, base64). Ciphertext is
  stored as `v1:<iv>:<tag>:<data>` so the scheme is versioned and keys are rotatable.
- **Never leave the server.** No API response includes token material. The dashboard is
  served token *status* (`valid | expiring | expired | revoked`) and expiry only.
- **Never hardcoded.** All credentials come from validated environment config. The app
  refuses to boot if `ENCRYPTION_KEY` or `SESSION_SECRET` is missing, short, or is a
  known placeholder value.
- **Passwords** are hashed with scrypt (per-user salt, timing-safe comparison).

## Authentication and authorization
- Sessions are opaque random 256-bit ids in `httpOnly`, `sameSite=lax`, `secure`
  (outside dev) cookies. Session records are server-side and individually revocable.
- RBAC: `OWNER > ADMIN > EDITOR > VIEWER`, enforced by a route-level guard.
  Account connection and disconnection, the kill switch, brand configuration and
  the audit log require `ADMIN`+. Scheduling a piece, running a pipeline stage on
  demand and retrying failed publishes require `EDITOR`+ — that is the editorial
  role, and holding it to `ADMIN` would mean nobody can move approved content
  without an administrator. Note the consequence: an `EDITOR` can cause a post to
  go out, but cannot connect, disconnect, or reconfigure an account.
- Every organization-scoped query is filtered by `organizationId` at the repository
  layer — multi-tenancy is enforced in data access, not by remembering to add a `where`.

## OAuth
- `state` is a signed, TTL-bounded value bound to the session — this is the CSRF defense
  for the callback and is verified before any token exchange. It is *not* single-use:
  there is no nonce store, so a signed state can be replayed within its TTL. The
  provider `code` that must accompany it is single-use, so a replay cannot complete a
  second exchange.
- Exact `redirect_uri` matching; no wildcards.
- Only the minimum scopes each capability needs are requested.
- Tokens are exchanged server-side only; the authorization code never reaches the browser.

## Outbound requests
The research pipeline follows links it did not choose — an RSS `<link>` is written by
whoever controls the feed — and it fetches them from inside the deployment network, then
stores the response body as source text the API returns. Unchecked, that is a readable
SSRF. Every such fetch goes through `safeFetch` (`packages/core/src/net.ts`), which
enforces:
- `http`/`https` only, and no credentials embedded in the URL.
- Every address the hostname resolves to must be publicly routable — loopback,
  link-local (including `169.254.169.254`), private, CGNAT, multicast and reserved ranges
  are refused, as are the IPv4 destinations inside `::ffff:`, NAT64 and 6to4 wrappers. One
  public answer alongside a private one is still a refusal, since the connection picks the
  address.
- Redirects are followed manually, up to three hops, and every hop is re-validated — a
  `302` to the metadata endpoint is otherwise the obvious bypass.

**Known residual risk, stated rather than papered over:** validation resolves the hostname
and then lets the platform `fetch` connect, so a DNS record that changes between those two
moments (rebinding) is not caught. Closing that needs connection-level address pinning,
which the platform fetch API does not expose. The guard removes the direct, scriptable
path; it is not a complete mitigation.

## Logging
Log redaction runs at two levels, because one is not enough:
- `redact.paths` censors known-sensitive *keys* (`accessToken`, `authorization`, …).
- A `pino` error serializer additionally scrubs credential-shaped `name=value` pairs and
  URL userinfo out of *string values*, at any depth. Key-path redaction never inspects a
  value, so a token embedded in a request URL passes straight through it. That was a real
  finding, not a hypothetical: `redactUrl` in the platform HTTP layer once covered
  `client_secret` but not `fb_exchange_token`, which carries a live Meta access token, and
  a failed refresh wrote a working token into the logs. `redactUrl` now matches parameter
  names by pattern, so credential-shaped parameters are redacted by default rather than
  only when someone remembers to add them.

## Transport and headers
HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, a restrictive CSP, and
`Referrer-Policy: strict-origin-when-cross-origin`. TLS terminates ahead of the app.

## Input validation
Every route body/query/param is parsed by a Zod schema at the boundary; handlers receive
parsed, typed values. Prisma parameterizes all SQL — no string-built queries anywhere.

## Rate limiting and abuse
Global and per-route limits on the API; stricter limits on auth and OAuth routes.
Outbound platform calls are governed by a per-account token-bucket that respects each
platform's documented limits, so the system cannot get the brand's account throttled.

## Audit
Every privileged action — connect, disconnect, publish, schedule, approve, kill-switch,
role change, brand change — writes an immutable `AuditLog` row with actor, action,
subject, IP, and a JSON diff.

## Operational rules
- No production social account is ever used in automated tests. Platform HTTP is mocked
  with `nock`; a guard in the test setup fails the suite if a real platform hostname is
  contacted.
- Least-privilege database user: no `SUPERUSER`, no DDL outside migrations.
- Dependencies are pinned; CI runs `pnpm audit`.

## Reporting
Email the repository owner. Please do not open a public issue for a vulnerability.
