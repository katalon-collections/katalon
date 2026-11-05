---
title: "Record CRUD And Publishing"
summary: "Katalon record endpoints share a CRUD pattern for primary records and add publication validation, guarded deletes, soft-delete tombstones, purge cleanup, search indexing, and procedure completion."
topics: [architecture, workflows, backend, records, publishing]
sources:
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
  - id: collections-api
    type: file
    path: backend/src/katalon/api/v1/collections.py
  - id: storage-locations-api
    type: file
    path: backend/src/katalon/api/v1/storage_locations.py
  - id: procedures-api
    type: file
    path: backend/src/katalon/api/v1/procedures.py
  - id: publish-service
    type: file
    path: backend/src/katalon/services/publish_service.py
  - id: pid-service
    type: file
    path: backend/src/katalon/services/pid_service.py
  - id: batch-service
    type: file
    path: backend/src/katalon/services/batch_service.py
  - id: relation-service
    type: file
    path: backend/src/katalon/services/relation_service.py
  - id: visibility
    type: file
    path: backend/src/katalon/core/visibility.py
  - id: purge-tasks
    type: file
    path: backend/src/katalon/workers/purge_tasks.py
  - id: delete-tests
    type: file
    path: backend/tests/test_delete_409.py
  - id: soft-delete-tests
    type: file
    path: backend/tests/integration/test_soft_delete.py
  - id: schema-service
    type: file
    path: backend/src/katalon/services/schema_service.py
  - id: schema-destructive-tests
    type: file
    path: backend/tests/integration/test_schema_destructive_changes.py
  - id: purge-relation-cleanup-tests
    type: file
    path: backend/tests/integration/test_purge_relation_cleanup.py
---

Record CRUD in Katalon is implemented across seven endpoint families: objects, entities, places, occurrences, collections, storage locations, and procedures. The five public inventory types share the same lifecycle: list with filters, create, read with visibility checks, update with optimistic locking, publish, soft delete, restore, trash listing, snapshot, and per-record audit log [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@collections-api]. Storage locations use the same tombstone, trash-list, restore, and purge contract but are internal records rather than public Portal content [@storage-locations-api]. Procedures use create/read/update/delete/snapshot/audit routes but replace publishing with domain-specific completion and procedure-state validation; procedure archiving is the reversible status change, while procedure deletion still removes the row [@procedures-api].

## Shared Record Pattern

List endpoints return a page object with `total`, `page`, `page_size`, and `items`, filter by status and subtype where available, apply public visibility for public collection record types, and search ID numbers plus JSONB metadata text when a query is supplied [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@collections-api]. Storage locations use the same ID/metadata search shape behind record permissions; procedure lists are not public-visibility filtered and add procedure type, due date, reference number, status, and reference-number filters [@storage-locations-api] [@procedures-api].

Create endpoints resolve or validate `idno`, normalize the subtype field, prepare metadata through the schema service, validate metadata with required fields skipped for drafts where the family supports drafts, and reject duplicate identifiers [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@collections-api] [@storage-locations-api] [@procedures-api]. Object records additionally validate `collection_status`; places translate latitude and longitude into a PostGIS point; procedures validate a fixed set of procedure types and statuses [@objects-api] [@places-api] [@procedures-api]. After the row is flushed, record endpoints mirror schema relation fields from `metadata_` into the generic relation table, write a `create` audit entry, mint PIDs only when the saved status is public, and then attempt Elasticsearch indexing where the type has public status [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@collections-api] [@storage-locations-api].

Update endpoints retrieve the row, call `require_version` against a mandatory `If-Match` (`428` if missing, `409` on mismatch), repeat identifier and metadata validation, capture old values, mutate scalars and `metadata_`, increment `version`, synchronize schema-defined relations, write an audit-log update entry, mint PIDs only when the old status was not public and the new status is public, and attempt to re-index the record [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@collections-api] [@storage-locations-api] [@procedures-api]. The form-side conflict resolution described in [Schema Driven Record Forms](schema-driven-record-forms) depends on that `409` version-conflict behavior; [Optimistic Locking](../../decisions/workflows/optimistic-locking) records the design boundary behind it.

`sync_schema_relations` deletes existing schema-derived outgoing relations for the record and recreates them from top-level and group-contained relation fields in current metadata, while preserving manually created relations with the same target and relation type [@relation-service]. Elasticsearch indexing is best effort on create/update for indexed record endpoints: exceptions are logged as warnings, so a successful database write can temporarily diverge from the search index until a later reindex reconciles it [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@collections-api] [@storage-locations-api].

## Publishing

Objects, entities, places, occurrences, and collections have `/publish` endpoints [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@collections-api]. Each endpoint calls `can_publish`, raises `422` with validation errors when the record cannot be published, then calls `publish_record` and commits [@objects-api] [@publish-service].

`can_publish` checks that the record type is one of the five public inventory models, that the row exists, that `idno` is present, and that metadata passes schema validation without skipping required fields [@publish-service]. `publish_record` then auto-mints missing PIDs before flipping the status: every active pid field with an explicitly configured `pid_provider` (`dnb_urn` or `ark`) and no stored value gets one PID minted, with the portal record URL as target; a mint failure returns `{"ok": false}` with the reason so publishing is blocked rather than silently publishing without a PID [@pid-service]. The same auto-mint hook runs on create/update endpoints when a record enters a public status directly and on batch `set_status` operations [@objects-api] [@batch-service]. `publish_record` sets `status` to `public`, writes a `publish` audit entry with `changed_fields={"status": "public"}`, and re-indexes the record [@publish-service]. Procedures and storage locations are excluded from the publish service model map, so their lifecycle is handled outside public publishing [@publish-service] [@procedures-api] [@storage-locations-api].

## Guarded Delete

Every delete endpoint requires an editor-or-admin user, checks whether the record exists, counts generic relations for that record, and returns `409` with `related_count` when relations exist and `force=true` was not supplied [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@collections-api] [@storage-locations-api] [@procedures-api]. The tests assert that delete routes require authentication, that `force=true` does not bypass authentication, and that object/entity relation conflicts return the expected `409` body shape [@delete-tests].

For objects, entities, places, occurrences, collections, and storage locations, delete is a tombstone operation: the endpoint sets `deleted_at`, writes a `delete` audit entry, and removes the search document. It deliberately retains generic relations and schema-embedded JSONB references so restoration is lossless. Admin restore routes clear `deleted_at`, write an `undelete` audit entry, and re-index the record; trash-list routes expose rows where `deleted_at` is set [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@collections-api] [@storage-locations-api] [@soft-delete-tests].

Soft-deleted collection rows stay hidden from ordinary queries because shared public visibility adds `deleted_at IS NULL` and because `ensure_publicly_visible()` returns `410 Gone` to anonymous callers for deleted rows while authenticated detail reads see a normal not-found response [@visibility]. The integration tests lock this down: a deleted public object returns `410` on `/portal/v1/objects/{id}`, `404` on authenticated `/v1/objects/{id}`, appears in trash, restores cleanly, and is not resurrected by Elasticsearch reconciliation or bulk reindexing [@soft-delete-tests].

Hard deletion happens two ways (#414). The nightly purge worker (`purge_soft_deleted`) permanently deletes soft-deleted objects, entities, places, occurrences, collections, and storage locations older than `AdminConfig.purge_retention_days` (default 30, admin-configurable under Einstellungen → Papierkorb) — the run is skipped entirely when `AdminConfig.auto_purge_enabled` is `false`. Admins can also hard-delete a single trashed record on demand via `POST /{id}/purge` (`require_role("admin")`, 404 if the record does not exist or is not currently soft-deleted), sharing the same deletion logic as the nightly sweep. For objects it also removes original and pyramid media files. Before deleting a target row, purge removes its generic relations and configured direct or group-contained JSONB references from every record type, writes a `relation_cleanup` audit entry for each changed source, queues source reindexing after the database commit, and then writes the target `purge` audit entry. The cleanup is idempotent, so retries do not create duplicate audits or dispatches [@purge-tasks] [@soft-delete-tests] [@purge-relation-cleanup-tests]. Procedure delete remains different: when forced it removes generic relations and configured JSONB references, writes a delete audit entry, deletes the procedure row, and removes it from search [@procedures-api].

Schema changes that touch existing metadata (`purge_field_data`, `migrate_translatable_shape`, `migrate_repeatable_shape`) run over every record of the target type regardless of `deleted_at` (#414) — a trashed record is migrated/purged at the same time as active ones, so a later restore never resurrects a value shape or field value that no longer matches the current schema [@schema-service]. Integration tests cover repeatable-field collapse followed by restore and save, plus purging top-level and group subfield values from both active and trashed objects [@schema-destructive-tests].

## Procedure Completion

Procedures add a domain operation at `POST /v1/procedures/{id}/complete` [@procedures-api]. The endpoint sets the procedure status to `completed`, optionally updates every linked object's `collection_status`, writes audit entries for each changed object and the procedure, and re-indexes the affected records [@procedures-api].

Procedure validation prevents unknown procedure types or statuses and rejects activation of a `loan_out` procedure when a linked object already has another active outgoing loan [@procedures-api]. That check makes loan-out status more than a label: activating it enforces a collection-management invariant across procedure-object relations [@procedures-api].

Audit entries and snapshots created by these endpoints are explained in [Audit And Snapshots](audit-and-snapshots).
