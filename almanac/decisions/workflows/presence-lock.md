---
title: "Presence Lock"
summary: "Katalon shows who else currently has a record open for editing and, in blocking mode, rejects saves from a second editor while that presence is active."
topics: [decisions, concurrency, records, frontend]
sources:
  - id: presence-service
    type: file
    path: backend/src/katalon/services/presence_service.py
  - id: presence-api
    type: file
    path: backend/src/katalon/api/v1/presence.py
  - id: presence-model
    type: file
    path: backend/src/katalon/core/models.py
  - id: admin-config-api
    type: file
    path: backend/src/katalon/api/v1/admin_config.py
  - id: objects-api
    type: file
    path: backend/src/katalon/api/v1/objects.py
  - id: admin-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: admin-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: admin-list
    type: file
    path: frontend/admin/src/components/screens/ScreenList.tsx
  - id: admin-settings
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: presence-tests
    type: file
    path: backend/tests/test_presence_service.py
  - id: issue-371
    type: web
    url: https://github.com/karkraeg/Katalon/issues/371
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/presence-lock.md
  - id: manual-lock-api
    type: file
    path: backend/src/katalon/api/v1/locks.py
  - id: manual-lock-service
    type: file
    path: backend/src/katalon/services/lock_service.py
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/presence-lock.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Presence Lock is a soft, ephemeral signal — separate from [Optimistic Locking](optimistic-locking) — that shows other users a record is currently open for editing, and optionally blocks a second save while that presence is active [@presence-service] [@presence-api]. It is Phase 1 of GitHub issue #371; Phase 2 (persistent manual exclusive locks with Force Unlock) is also implemented, as a separate mechanism [@manual-lock-api] [@manual-lock-service]. Issue #371 supplies historical context rather than current completion evidence [@issue-371].

## Context

Optimistic locking already prevents a stale save from silently overwriting another user's change, but it only surfaces the conflict at save time. Nothing told a second curator, while they were still typing, that someone else had the same record open — the first sign of trouble was a 409 after minutes of work. Presence Lock closes that gap without replacing the existing version-based conflict protection [@presence-service].

## Decision

**Generic `edit_presence` table, not one row shape per record type.** A single table keyed by `resource_type` + `resource_id` + `session_id` covers all seven core record types, matching the existing generic pattern used by `relations` [@presence-model]. `session_id` is a random id generated per browser tab and stored in `sessionStorage`, so two tabs of the same user do not collide and each expires independently [@admin-client].

**Heartbeat + TTL instead of an explicit close signal.** The Admin form heartbeats every 25 seconds while an existing record's edit form is mounted; a row counts as active only if `last_seen_at` is within the last 60 seconds [@presence-service] [@admin-form]. There is no cleanup worker — stale rows are simply filtered out of every query and get overwritten by the next heartbeat elsewhere. This trades a slightly stale "still editing" signal (up to ~60s after a crashed tab) for zero background job infrastructure.

**Admin-configurable mode, enforced server-side.** `AdminConfig.presence_lock_mode` is `"warning"` (default) or `"blocking"` [@admin-config-api]. In both modes the Admin form shows a banner naming the other editor(s) [@admin-form] and list views show a badge on affected rows [@admin-list]. In blocking mode, `enforce_not_blocked()` additionally raises `409 {"error": "presence_locked", "locked_by": ...}` from every record type's update endpoint before the version check's payload is applied, so the restriction cannot be bypassed by calling the API directly instead of using the form [@presence-service] [@objects-api]. The mode is edited under Admin-Settings → "Bearbeitungssperre" [@admin-settings].

**No new role or lock-ownership model.** Presence Lock does not gate who may edit — it only informs and, in blocking mode, temporarily rejects a second writer while a presence is active. The separate manual exclusive lock uses persistent ownership, an optional reason and expiry, own release and admin force-unlock. Its creation is gated by `manual_lock`; blocked writes raise `resource_locked`, distinct from `presence_locked` [@manual-lock-api] [@manual-lock-service]. The original issue discussed governance against Katalon's real role names (`viewer`/`cataloger`/`editor`/`admin`/`superuser`, not the `Curator`/`Data Entry` names from the original feature draft) [@issue-371].

## Consequences

Presence conflicts are visible before a save is attempted, which should cut down on the version-conflict merge dialog firing in the first place for records with multiple simultaneous editors.

Blocking mode is enforced per-request, not per-session — a user who closes their blocking-mode presence (tab close, 60s timeout) immediately frees the record for others, there is no grace period. Reused, generic infrastructure (`RECORD_TYPES`, `_RECORD_MODELS`-style resource typing) keeps this a single new table and one new router rather than seven parallel presence tables [@presence-service] [@presence-tests].
