---
type: Decision
title: "Auth Token Architecture"
tags: [architecture, documentation]
timestamp: 2026-10-30T00:00:00Z
origin: almanac/decisions/platform/auth-token-architecture.md
consolidated: 2026-10-30
---

## Context

Login uses JWT access tokens plus a refresh token, not a classic server-side session store [1]. That shape matters because Katalon has two browser clients, Admin and Portal, and Portal staff authentication deliberately reuses the same account and token flow instead of creating a separate identity system [3]. The main security question is token storage: OWASP warns against putting session identifiers or sensitive data in browser local storage, while RFC 8725 defines JWT handling pitfalls for bearer-token systems [4] [5].

## Decision

Keep the existing hybrid: a JWT access token held only in an in-memory frontend module variable, paired with a refresh token in an `HttpOnly`, `Secure` when not `debug`, `SameSite=Strict` cookie, rotated via `/v1/auth/refresh` and revocable per user via `token_version` [1] [2]. This keeps JavaScript away from the durable refresh credential while avoiding a server-side session store. `localStorage.removeItem('katalon_token')` calls in `client.ts` are cleanup of a pre-refresh-token legacy scheme, not evidence of current localStorage token storage [2] [4].

Future SSO should integrate at the backend and then issue the same internal access/refresh-token pair. OpenID Connect already defines an ID Token as a JWT, so this architecture fits OIDC without replacing the browser storage model [6]. Issue #182 remains the LDAP/SSO work item; it should add an identity-provider entry point, not convert Katalon to server-side sessions first [7].

## Consequences

Do not migrate to server-side sessions by default. `access_token_expire_minutes` defaults to 60 minutes (was 480 until 2026-09-26). Logout only clears the cookie and does not revoke tokens server-side, so a leaked access token would otherwise stay usable for a full workday on production instances; 60 minutes bounds that window. Users are not signed out by this: the client renews the access token silently from the 30-day rolling refresh cookie on `401` and on page load, including in `uploadWithProgress` [1] [2]. Revocation of all of a user's tokens stays available through `token_version` (password change/reset, `POST /v1/auth/logout-others`). Refresh-token reuse detection and a device list were rejected: they need a session table and race with concurrent refreshes from several tabs. Portal keeps sharing the same cookie/token flow rather than adding a portal-specific login system [3].

# Citations

[1] backend/src/katalon/api/v1/auth.py
[2] frontend/admin/src/api/client.ts
[3] almanac/decisions/frontend/staff-portal-authentication.md
[4] https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html
[5] https://www.rfc-editor.org/rfc/rfc8725.html
[6] https://openid.net/specs/openid-connect-core-1_0.html
[7] https://github.com/karkraeg/Katalon/issues/182
