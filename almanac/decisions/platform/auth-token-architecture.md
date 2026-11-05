---
title: "Auth Token Architecture"
summary: "Access token in memory plus an HttpOnly/Secure/SameSite=Strict refresh cookie is the deliberate browser login design, not a placeholder to revisit."
topics: [decisions, platform, security, authentication]
sources:
  - id: auth-api
    type: file
    path: backend/src/katalon/api/v1/auth.py
  - id: admin-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: staff-portal-auth
    type: file
    path: almanac/decisions/frontend/staff-portal-authentication.md
  - id: owasp-html5-storage
    type: web
    url: https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
  - id: oidc-core
    type: web
    url: https://openid.net/specs/openid-connect-core-1_0.html
  - id: sso-issue
    type: web
    url: https://github.com/karkraeg/Katalon/issues/182
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/auth-token-architecture.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/auth-token-architecture.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.



## Current Contract

Keep the existing hybrid: a JWT access token held only in an in-memory frontend module variable, paired with a refresh token in an `HttpOnly`, `Secure` when not `debug`, `SameSite=Strict` cookie, rotated via `/v1/auth/refresh` and revocable per user via `token_version` [@auth-api] [@admin-client]. This keeps JavaScript away from the durable refresh credential while avoiding a server-side session store. `localStorage.removeItem('katalon_token')` calls in `client.ts` are cleanup of a pre-refresh-token legacy scheme, not evidence of current localStorage token storage [@admin-client] [@owasp-html5-storage].

Future SSO should integrate at the backend and then issue the same internal access/refresh-token pair. OpenID Connect already defines an ID Token as a JWT, so this architecture fits OIDC without replacing the browser storage model [@oidc-core]. Issue #182 remains the LDAP/SSO work item; it should add an identity-provider entry point, not convert Katalon to server-side sessions first [@sso-issue].

## Implementation Constraints

Do not migrate to server-side sessions by default. `access_token_expire_minutes` defaults to 60 minutes (was 480 until 2026-09-26). Logout only clears the cookie and does not revoke tokens server-side, so a leaked access token would otherwise stay usable for a full workday on production instances; 60 minutes bounds that window. Users are not signed out by this: the client renews the access token silently from the 30-day rolling refresh cookie on `401` and on page load, including in `uploadWithProgress` [@auth-api] [@admin-client]. Revocation of all of a user's tokens stays available through `token_version` (password change/reset, `POST /v1/auth/logout-others`). Refresh-token reuse detection and a device list were rejected: they need a session table and race with concurrent refreshes from several tabs. Portal keeps sharing the same cookie/token flow rather than adding a portal-specific login system [@staff-portal-auth].
