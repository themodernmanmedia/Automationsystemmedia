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
- RBAC: `OWNER > ADMIN > EDITOR > VIEWER`, enforced by a route-level guard. Publishing
  and account-connection require `ADMIN`+; the kill switch requires `ADMIN`+.
- Every organization-scoped query is filtered by `organizationId` at the repository
  layer — multi-tenancy is enforced in data access, not by remembering to add a `where`.

## OAuth
- `state` is a signed, single-use, TTL-bounded value bound to the session — this is the
  CSRF defense for the callback and is verified before any token exchange.
- Exact `redirect_uri` matching; no wildcards.
- Only the minimum scopes each capability needs are requested.
- Tokens are exchanged server-side only; the authorization code never reaches the browser.

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
