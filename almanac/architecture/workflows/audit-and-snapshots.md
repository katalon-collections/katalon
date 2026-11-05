---
title: "Audit And Snapshots"
summary: "Katalon records keep append-only audit entries for actions and optional JSON snapshots that can restore selected record state."
topics: [architecture, workflows, backend, audit, snapshots, records]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: audit-service
    type: file
    path: backend/src/katalon/services/audit_service.py
  - id: audit-api
    type: file
    path: backend/src/katalon/api/v1/audit.py
  - id: concurrency-helper
    type: file
    path: backend/src/katalon/core/concurrency.py
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
  - id: relations-api
    type: file
    path: backend/src/katalon/api/v1/relations.py
  - id: dependencies
    type: file
    path: backend/src/katalon/core/dependencies.py
  - id: visibility
    type: file
    path: backend/src/katalon/core/visibility.py
  - id: seed-demo
    type: file
    path: backend/scripts/seed_demo.py
  - id: optimistic-tests
    type: file
    path: backend/tests/test_optimistic_locking.py
  - id: snapshot-integrity-tests
    type: file
    path: backend/tests/integration/test_snapshot_integrity.py
---

Audit and snapshots are two separate persistence mechanisms around record changes. Audit entries are append-only rows in `audit_log` with a record identity, optional user id, action name, JSON `changed_fields`, and timestamp; snapshots are labeled JSON payloads in `record_snapshots` for a record identity and creator [@models]. CRUD and workflow endpoints write audit entries as changes happen, while editors create snapshots explicitly and can restore selected scalar and metadata state from those snapshots for collection records through the same version boundary used for destructive state replacement [@objects-api] [@concurrency-helper]. Procedures have audit entries but no snapshot API or UI.

## Audit Model And Querying

`AuditLog` stores `record_type`, `record_id`, `user_id`, `action`, `changed_fields`, and `created_at`, with an index over `record_type` and `record_id` for per-record lookup [@models]. The `log_change` service creates this row and leaves commit ownership to the surrounding request session [@audit-service]. That lets create, update, publish, delete, and completion code write audit entries without owning transaction boundaries [@audit-service].

The global audit endpoints (`GET /v1/audit` and `GET /v1/audit/search`) require the `audit_log` feature and additionally restrict results to the record types the caller may read: each of the seven role-permissioned record types is checked against `readable_record_types()`, while audit domains outside that set (`user`, `schema`, `sparql`, lock targets) stay unfiltered [@audit-api] [@dependencies] [@visibility]. `GET /v1/audit/search` additionally searches current record identifiers and metadata, audit payloads, users, actions, and UUIDs, with date filters and server-side pagination; this keeps the admin audit view usable after large migrations. It also resolves record labels per type from the current record tables, including collections and storage locations, and strips a relation-change diff's `related_record_id`/`related_record_type`/`related_record_label` whenever the caller cannot read that related record's type — mirroring the relation-list guard below [@audit-api] [@relations-api]. Per-record audit routes in record endpoint modules (`objects`, `entities`, `places`, `occurrences`, `procedures`, `collections`) require read permission on that specific record and forward the resolved user into the same audit-listing helper [@objects-api] [@dependencies].

## Changed Field Payloads

Create and delete actions often write an empty `changed_fields` object, while update actions store old and new values chosen by each endpoint [@audit-service] [@objects-api]. Object updates record old idno, object type, collection status, status, and metadata, then record new object type, collection status, status, and metadata [@objects-api]. Procedure updates record old scalar fields and metadata, then store the validated `ProcedureRead` output as the new state.

The demo seed script bypasses HTTP CRUD endpoints, so it explicitly calls `log_change` after flushing seeded places, entities, occurrences, and objects. It chooses an existing admin or superuser as `user_id` and writes `create` actions without `changed_fields`, matching the endpoint create pattern while keeping seeded records visible in the Audit tab [@seed-demo] [@audit-service].

Publishing writes an action named `publish` with `changed_fields` set to the new public status through the publish service, and procedure completion writes one audit entry for the procedure plus one object update entry for every linked object whose collection status changes. Those audit rows describe what happened; they are not the mechanism that restores state.

## Snapshots

`RecordSnapshot` stores `record_type`, `record_id`, `label`, JSON `snapshot`, optional `created_by`, and `created_at` [@models]. Object snapshot creation copies idno, object type, collection status, status, and metadata [@objects-api]. Other collection record types follow the same smaller pattern for their subtype, status, and metadata fields [@entities-api] [@places-api] [@occurrences-api]. Procedures deliberately have no snapshot endpoints. Historical rows with `record_type = "procedure"` are retained rather than destructively purged, but no endpoint or form exposes them.

Snapshot listing requires read permission on the record's type, using the same per-type role-permission check as other read endpoints; it previously took no user dependency at all, so any request — authenticated or not — could read full historical metadata [@objects-api] [@dependencies]. Restoring an object snapshot requires `If-Match`, copies back only keys present in the snapshot, including idno, status, object type, collection status, and metadata, flushes the versioned record, synchronizes schema-driven relation fields, writes a `restore` audit entry with the `snapshot_id`, commits, and then tries to reindex the record in Elasticsearch [@objects-api]. Entity, place, occurrence, and collection restore endpoints follow the same pattern for their type-specific scalar field, status, and metadata [@entities-api] [@places-api] [@occurrences-api] [@collections-api].

## Version Boundary

Primary record models carry an integer `version` column with default `1`, and SQLAlchemy treats that column as the mapper's version id, so successful flushes of changed collection records advance it [@models]. `check_version()` is the shared 409-on-mismatch comparison; called directly it skips a missing header, but the optimistic-locking tests also cover `require_version()`, the helper every update, publish, and snapshot-restore endpoint actually calls: it raises `428` when `If-Match` is missing and otherwise delegates to `check_version()` [@optimistic-tests].

Snapshot restore and ordinary record updates now share the same `require_version()` contract — missing `If-Match` raises `428`, a stale version raises `409`, and a successful call increments the record version; integration tests cover that contract for restore across all four collection record types and separately assert object restore writes an audit entry [@concurrency-helper] [@snapshot-integrity-tests] [@objects-api]. There is no longer a compatibility distinction between the two paths for [Record CRUD And Publishing](record-crud-and-publishing): both require callers to participate in the version protocol, since no known installation predates the change.
