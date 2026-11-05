---
title: "Optimistic Locking"
summary: "Katalon uses integer record versions, If-Match headers, and an Admin three-way merge dialog to prevent silent overwrite during parallel edits."
topics: [decisions, concurrency, records, frontend]
sources:
  - id: decision-note
    type: file
    path: .agents/knowledge/decisions/optimistic-locking.md
  - id: concurrency-helper
    type: file
    path: backend/src/katalon/core/concurrency.py
  - id: record-models
    type: file
    path: backend/src/katalon/core/models.py
  - id: objects-api
    type: file
    path: backend/src/katalon/api/v1/objects.py
  - id: entities-api
    type: file
    path: backend/src/katalon/api/v1/entities.py
  - id: places-api
    type: file
    path: backend/src/katalon/api/v1/places.py
  - id: occurrences-api
    type: file
    path: backend/src/katalon/api/v1/occurrences.py
  - id: procedures-api
    type: file
    path: backend/src/katalon/api/v1/procedures.py
  - id: admin-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: admin-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: locking-tests
    type: file
    path: backend/tests/test_optimistic_locking.py
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/optimistic-locking.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/optimistic-locking.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Katalon uses optimistic locking to stop one curator's save from silently overwriting another curator's parallel edit. Each primary record and procedure has an integer `version`, update endpoints compare that version with the request's `If-Match` header, and stale saves return a structured 409 response instead of accepting last-write-wins [@record-models] [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@procedures-api] [@concurrency-helper]. The Admin form handles that 409 by fetching the current server record and merging metadata field by field, asking the user only when both sides changed the same field [@admin-form]. This decision constrains [Schema-Driven Record Forms](../../architecture/workflows/schema-driven-record-forms) because the form is part of the data-integrity contract, not only a display surface.

## Context

The recorded decision came from a production-readiness concern: Katalon's update APIs replace the record payload, including `metadata_`, so two users editing the same record could lose work if the second save overwrote the first without noticing [@decision-note]. That risk is especially important in a metadata management system because repeatable metadata fields can contain the work being curated, not just a minor display preference.

The project chose an integer token instead of `updated_at` as the comparison value. The decision note rejects timestamp ETags because timezone, serialization, and microsecond round-trips are fragile, while a monotonically increasing integer has one meaning across backend and frontend [@decision-note]. The current SQLAlchemy models carry `version` on all seven core types with default value `1` [@record-models].

## Decision

Updates use optimistic locking rather than server-side edit locks. Backend update endpoints for all seven core types read `If-Match` and call `require_version()`, which raises `428` when the header is missing and otherwise delegates to `check_version()` for the `409` mismatch comparison, then increment the stored `version` after a successful update [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@procedures-api]. `If-Match` is mandatory on every record update, publish, and snapshot-restore endpoint — there is no header-optional path left for REST callers; `check_version()` itself still skips a missing header when called directly, but no route calls it directly anymore, only `require_version()` does [@concurrency-helper]. Backend tests lock that contract down with separate cases for missing headers (`428`), matching versions, and stale versions that raise HTTP 409 with `{"error": "version_conflict", "current_version": ...}` [@locking-tests].

The Admin API client sends `If-Match` when a version argument is present and translates the backend's `version_conflict` detail into `VersionConflictError` [@admin-client]. Record update calls accept the optional version parameter for the mutable record families, so the form can use the same conflict path across the editor [@admin-client].

The Admin form resolves conflicts with a metadata-level three-way merge. On `VersionConflictError`, it fetches the current server record, compares loaded base values, server metadata, and the user's current values, then auto-merges fields changed by only one side [@admin-form]. If both server and user changed a metadata field differently, `ConflictDialog` lets the user pick the stored value or their value for that field, and `commitMerge()` saves the merged metadata with the newest server version [@admin-form].

## Consequences

The main benefit is that ordinary parallel editing no longer loses work silently. A stale save either merges cleanly in the Admin form or becomes an explicit field-level choice, while unchanged user edits remain in React state during conflict handling [@admin-form].

There is no compatibility opt-out for REST callers: any client updating a record, publishing it, or restoring a snapshot must send `If-Match`, including scripts and external integrations, since no known installation predates this contract. The importer and batch-edit Celery tasks are unaffected for a different reason — they write through the service layer directly and never call these HTTP endpoints, so there is no per-record "expected version" for them to send in the first place; that is a structural bypass, not a header-optional path [@concurrency-helper].

The merge scope is intentionally metadata-field level. The decision note records that repeatable fields are treated as whole field values and that scalar fields outside metadata are not given the same interactive merge UI [@decision-note]. Future changes to [Audit And Snapshots](../../architecture/workflows/audit-and-snapshots) should preserve the version check before update and should not replace the conflict response with blind reload or forced overwrite.
