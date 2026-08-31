---
title: "Cantaloupe Auth Gate"
summary: "Katalon protects IIIF tiles and thumbnails with nginx auth_request because Cantaloupe has no record-level authorization."
topics: [decisions, operations, media, iiif, security]
sources:
  - id: media-api
    type: file
    path: backend/src/katalon/api/v1/media.py
  - id: nginx-conf
    type: file
    path: docker/nginx.conf
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
---

Katalon gates Cantaloupe behind nginx instead of exposing `/iiif/` directly. The decision exists because Cantaloupe serves image derivatives by storage identifier and does not know whether a Katalon object or individual `MediaFile` is public. The backend therefore owns the visibility check, and nginx calls that backend check before proxying any tile or thumbnail request [@nginx-conf] [@media-api].

## Context

Object visibility and per-file media visibility are separate rules. A public object can have individual hidden files through `MediaFile.is_public`, and staff users may still need those files in Admin or in the authenticated Portal view [@media-api]. If `/iiif/` bypasses the API, a caller that knows or discovers the IIIF identifier can fetch a hidden derivative even when the object metadata path is correctly filtered.

## Decision

The outer nginx route for `/iiif/` uses `auth_request /internal/media-authorize`. That internal route forwards the original URI and bearer token to `GET /v1/media/_authorize`, where the backend resolves the encoded IIIF identifier to a `MediaFile`, loads its parent object, re-runs object visibility, and rejects anonymous access to `is_public = false` files before nginx proxies to Cantaloupe [@nginx-conf] [@media-api].

Thumbnail redirects stay host-relative (`/iiif/...`) rather than using the configured public Cantaloupe base URL. The Admin form fetches thumbnails through `authorizedFetch()` into blobs because a plain image tag cannot attach the bearer token required by the nginx gate [@media-api] [@screen-form].

## Consequences

Future IIIF routes must preserve the backend authorization step whenever they expose Cantaloupe derivatives. Kubernetes or custom ingress deployments must recreate the same gate before serving instances with hidden media; a route that sends `/iiif/` straight to Cantaloupe is only acceptable for fully public media sets.
