---
title: "Usage Statistics"
summary: "Anonymous per-day view and download counters for public records: portal beacon, download counting, global and portal switches, admin display, and purge cleanup."
topics: [architecture, workflows, portal, privacy, media, admin]
sources:
  - id: usage-service
    type: file
    path: backend/src/katalon/services/usage_service.py
  - id: portal-public
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
  - id: usage-api
    type: file
    path: backend/src/katalon/api/v1/usage.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: migration
    type: file
    path: backend/migrations/versions/0087_record_usage_stats.py
  - id: purge-tasks
    type: file
    path: backend/src/katalon/workers/purge_tasks.py
  - id: detail-layout
    type: file
    path: frontend/portal/src/components/DetailPageLayout.tsx
  - id: record-usage-line
    type: file
    path: frontend/admin/src/components/RecordUsageLine.tsx
  - id: settings
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: decision
    type: file
    path: .agents/knowledge/decisions/nutzungsstatistik-tageszaehler-und-beacon.md
  - id: tests
    type: file
    path: backend/tests/integration/test_usage_stats.py
---

Katalon counts how often public records are viewed in the Portal and how often their media files are downloaded. Counters live in `record_usage_daily`, one row per record type, record id and UTC day with `views` and `downloads`; every event is one atomic `INSERT … ON CONFLICT DO UPDATE`, safe across API workers. No IP address, cookie, device id or session is stored. The table has no foreign key (it covers several record tables), so purging a record deletes its rows explicitly [@usage-service] [@models] [@migration] [@purge-tasks]. The decision record (beacon instead of counting the detail `GET`, day rows instead of a Redis buffer) lives in the OKF knowledge base [@decision].

## What Is Counted

Views are counted by a beacon, not by the detail `GET`: anonymous detail reads are publicly cacheable for 60 s and the Portal reuses the detail endpoints for relation titles, so a server-side counter there would be wrong in both directions. `DetailPageLayout` (objects, entities, places, occurrences) and `CollectionDetailPage` render `UsageStats`, which sends `POST /portal/v1/usage/{plural_type}/{id}/view` once per record id. The endpoint applies the public visibility rules (404 for drafts or deleted records unless the caller has read permission), is rate-limited like public search, and counts only when the caller is not staff and the user agent does not look like a bot [@portal-public] [@detail-layout] [@usage-service].

Downloads are counted in `GET /portal/v1/media/{id}/download` against the owning object, for anonymous non-bot callers and not for resumed range requests (`Range` past byte 0). The endpoint itself requires `PortalConfig.media_download_enabled` for anonymous callers, see [Media And IIIF](media-and-iiif). Inline `/file` reads and IIIF image requests are never counted [@portal-public].

## Switches And Display

`AdminConfig.usage_stats_enabled` (default `true`) is the global switch: when off, nothing is counted, the beacon answers 204, and the Admin hides the counters. Stored rows are kept. `PortalConfig.show_usage_stats` (default `false`) decides whether the beacon response carries `{views, downloads}`; `downloads` is `null` for non-objects or when downloads are off, and the sidebar then shows only the views row. `GET /portal/v1/portal/config` mirrors the global switch as read-only `usage_stats_enabled` [@portal-public] [@models].

In the Admin, `RecordUsageLine` in the record form toolbar calls `GET /v1/usage/{record_type}/{id}` (record read permission) and shows all-time views and, when non-zero, downloads, with last-30-days numbers in the tooltip. Settings → Portal holds the two portal checkboxes in the detail layout card and a separate "Nutzungsstatistik" card for the global switch, which saves immediately [@usage-api] [@record-usage-line] [@settings].

Counts are guidance, not audited figures: the beacon is an anonymous POST, so the rate limit bounds but cannot prevent inflation [@tests].
