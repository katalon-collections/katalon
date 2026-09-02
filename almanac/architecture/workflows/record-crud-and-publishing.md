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
---

Record CRUD in Katalon is implemented as five endpoint families: objects, entities, places, occurrences, and procedures. The four public collection types share the same lifecycle: list with filters, create, read with visibility checks, update with optimistic locking, publish, soft delete, restore, trash listing, snapshot, and per-record audit log [@objects-api] [@entities-api] [@places-api] [@occurrences-api]. Procedures use create/read/update/delete/snapshot/audit routes but replace publishing with domain-specific completion and procedure-state validation; procedure archiving is the reversible status change, while procedure deletion still removes the row [@procedures-api].

## Shared Record Pattern

List endpoints return a page object with `total`, `page`, `page_size`, and `items`, filter by status and subtype where available, apply public visibility for collection record types, and search through `search_vector.match(q)` when a query is supplied [@objects-api] [@entities-api] [@places-api] [@occurrences-api]. Procedure lists are not public-visibility filtered and add procedure type, due date, reference number, status, and full-text filters [@procedures-api].

Create endpoints resolve or validate `idno`, normalize the subtype field, prepare metadata through the schema service, validate metadata with required fields skipped for drafts, and reject duplicate identifiers [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@procedures-api]. Object records additionally validate `collection_status`; places translate latitude and longitude into a PostGIS point; procedures validate a fixed set of procedure types and statuses [@objects-api] [@places-api] [@procedures-api]. After the row is flushed, the four collection record endpoints mirror schema relation fields from `metadata_` into the generic relation table, write a `create` audit entry, mint PIDs only when the saved status is public, and then attempt Elasticsearch indexing [@objects-api] [@entities-api] [@places-api] [@occurrences-api].

Update endpoints retrieve the row, call `check_version` against `If-Match`, repeat identifier and metadata validation, capture old values, mutate scalars and `metadata_`, increment `version`, synchronize schema-defined relations, write an audit-log update entry, mint PIDs only when the old status was not public and the new status is public, and attempt to re-index the record [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@procedures-api]. The form-side conflict resolution described in [Schema Driven Record Forms](schema-driven-record-forms) depends on that `409` version-conflict behavior; [Optimistic Locking](../../decisions/workflows/optimistic-locking) records the design boundary behind it.

`sync_schema_relations` deletes existing schema-derived outgoing relations for the record and recreates them from top-level and group-contained relation fields in current metadata, while preserving manually created relations with the same target and relation type [@relation-service]. Elasticsearch indexing is best effort on create/update for the collection endpoints: exceptions are logged as warnings, so a successful database write can temporarily diverge from the search index until a later reindex reconciles it [@objects-api] [@entities-api] [@places-api] [@occurrences-api].

## Publishing

Only objects, entities, places, and occurrences have `/publish` endpoints [@objects-api] [@entities-api] [@places-api] [@occurrences-api]. Each endpoint calls `can_publish`, raises `422` with validation errors when the record cannot be published, then calls `publish_record` and commits [@objects-api] [@publish-service].

`can_publish` checks that the record type is one of the four collection models, that the row exists, that `idno` is present, and that metadata passes schema validation without skipping required fields [@publish-service]. `publish_record` then auto-mints missing PIDs before flipping the status: every active pid field with an explicitly configured `pid_provider` (`dnb_urn` or `ark`) and no stored value gets one PID minted, with the portal record URL as target; a mint failure returns `{"ok": false}` with the reason so publishing is blocked rather than silently publishing without a PID [@pid-service]. The same auto-mint hook runs on create/update endpoints when a record enters a public status directly and on batch `set_status` operations [@objects-api] [@batch-service]. `publish_record` sets `status` to `public`, writes a `publish` audit entry with `changed_fields={"status": "public"}`, and re-indexes the record [@publish-service]. Procedures are excluded from the publish service model map, so their lifecycle is handled by status updates and completion instead [@publish-service] [@procedures-api].

## Guarded Delete

Every delete endpoint requires an editor-or-admin user, checks whether the record exists, counts generic relations for that record, and returns `409` with `related_count` when relations exist and `force=true` was not supplied [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@procedures-api]. The tests assert that delete routes require authentication, that `force=true` does not bypass authentication, and that object/entity relation conflicts return the expected `409` body shape [@delete-tests].

For objects, entities, places, and occurrences, delete is a tombstone operation: the endpoint sets `deleted_at`, writes a `delete` audit entry, removes the search document, and enqueues `cleanup_relation_refs` for schema-embedded relation references [@objects-api] [@entities-api] [@places-api] [@occurrences-api]. Admin restore routes clear `deleted_at`, write an `undelete` audit entry, and re-index the record; trash-list routes expose rows where `deleted_at` is set [@objects-api] [@entities-api] [@places-api] [@occurrences-api].

Soft-deleted collection rows stay hidden from ordinary queries because shared public visibility adds `deleted_at IS NULL` and because `ensure_publicly_visible()` returns `410 Gone` to anonymous callers for deleted rows while authenticated detail reads see a normal not-found response [@visibility]. The integration tests lock this down: a deleted public object returns `410` on `/portal/v1/objects/{id}`, `404` on authenticated `/v1/objects/{id}`, appears in trash, restores cleanly, and is not resurrected by Elasticsearch reconciliation or bulk reindexing [@soft-delete-tests].

Hard deletion is deferred to the purge worker. `purge_soft_deleted` permanently deletes soft-deleted objects, entities, places, and occurrences older than `settings.purge_after_days`; for objects it also removes original and pyramid media files, deletes generic relations, and writes a `purge` audit entry before deleting the row [@purge-tasks] [@soft-delete-tests]. Procedure delete remains different: when forced it removes generic relations, writes a delete audit entry, deletes the procedure row, removes it from search, and enqueues metadata relation cleanup [@procedures-api].

## Procedure Completion

Procedures add a domain operation at `POST /v1/procedures/{id}/complete` [@procedures-api]. The endpoint sets the procedure status to `completed`, optionally updates every linked object's `collection_status`, writes audit entries for each changed object and the procedure, and re-indexes the affected records [@procedures-api].

Procedure validation prevents unknown procedure types or statuses and rejects activation of a `loan_out` procedure when a linked object already has another active outgoing loan [@procedures-api]. That check makes loan-out status more than a label: activating it enforces a collection-management invariant across procedure-object relations [@procedures-api].

Audit entries and snapshots created by these endpoints are explained in [Audit And Snapshots](audit-and-snapshots).
