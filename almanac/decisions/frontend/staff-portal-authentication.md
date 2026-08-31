---
title: "Staff Portal Authentication"
summary: "Portal staff reuse existing Katalon accounts while anonymous visitors retain the public projection."
topics: [decisions, frontend, portal, authentication]
sources:
  - id: portal-client
    type: file
    path: frontend/portal/src/api/client.ts
  - id: portal-app
    type: file
    path: frontend/portal/src/App.tsx
  - id: portal-public
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
---

## Context

Staff need to inspect internal records and non-public schema fields in the Portal without creating another identity system. Public self-registration, saved lists, saved searches, workspaces, and comments remain a separate future account product.

## Decision

The Portal reuses `/v1/auth/token` and the existing access/refresh tokens. Its read endpoints remain anonymous by default, but accept JWTs for the current staff roles. Only the explicit staff-role set gets internal record (subject to its existing backend read permission), schema, and search projections; an unknown future role stays on the anonymous projection [@portal-client] [@portal-public].

## Consequences

There is no new user table, registration endpoint, cookie/session backend, or portal-specific permission model. The Portal and Admin share the same browser token names on one origin. The login page may visibly reserve a disabled registration action, but public-account features, Procedures, and authenticated media/IIIF workspaces are not part of this decision [@portal-app] [@portal-public].
