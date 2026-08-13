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
  - id: optimistic-tests
    type: file
    path: backend/tests/test_optimistic_locking.py
---

Audit and snapshots are two separate persistence mechanisms around record changes. Audit entries are append-only rows in `audit_log` with a record identity, optional user id, action name, JSON `changed_fields`, and timestamp; snapshots are labeled JSON payloads in `record_snapshots` for a record identity and creator [@models]. CRUD and workflow endpoints write audit entries as changes happen, while editors create snapshots explicitly and can restore selected scalar and metadata state from those snapshots for collection records [@objects-api]. Procedures have audit entries but no snapshot API or UI.

## Audit Model And Querying

`AuditLog` stores `record_type`, `record_id`, `user_id`, `action`, `changed_fields`, and `created_at`, with an index over `record_type` and `record_id` for per-record lookup [@models]. The `log_change` service creates this row and leaves commit ownership to the surrounding request session [@audit-service]. That lets create, update, publish, delete, and completion code write audit entries without owning transaction boundaries [@audit-service].

The global audit endpoint filters by record type, record id, user id, action, and limit, then joins users for display names [@audit-api]. It also resolves record labels per type from the current record tables: object idno or title, entity name, place name, occurrence title, and procedure idno or reference number [@audit-api]. Per-record audit routes in record endpoint modules call the same `list_audit_log` helper with their fixed type and id [@objects-api].

## Changed Field Payloads

Create and delete actions often write an empty `changed_fields` object, while update actions store old and new values chosen by each endpoint [@audit-service] [@objects-api]. Object updates record old idno, object type, collection status, status, and metadata, then record new object type, collection status, status, and metadata [@objects-api]. Procedure updates record old scalar fields and metadata, then store the validated `ProcedureRead` output as the new state.

Publishing writes an action named `publish` with `changed_fields` set to the new public status through the publish service, and procedure completion writes one audit entry for the procedure plus one object update entry for every linked object whose collection status changes. Those audit rows describe what happened; they are not the mechanism that restores state.

## Snapshots

`RecordSnapshot` stores `record_type`, `record_id`, `label`, JSON `snapshot`, optional `created_by`, and `created_at` [@models]. Object snapshot creation copies idno, object type, collection status, status, and metadata [@objects-api]. Other collection record types follow the same smaller pattern for their subtype, status, and metadata fields [@entities-api] [@places-api] [@occurrences-api]. Procedures deliberately have no snapshot endpoints. Historical rows with `record_type = "procedure"` are retained rather than destructively purged, but no endpoint or form exposes them.

Snapshot listing queries by the fixed record type and id and orders newest first [@objects-api]. Restoring an object snapshot copies back only keys present in the snapshot, including idno, status, object type, collection status, and metadata, then flushes the session [@objects-api].

Restore endpoints do not write audit entries or increment version in the code shown here [@objects-api]. A future change that needs restore events to appear in audit history should add explicit `log_change` calls and version increments in each restore endpoint rather than relying on the snapshot row itself.

## Version Boundary

Primary record models carry an integer `version` column with default `1`, and update endpoints increment it after a successful optimistic-locking check [@models] [@objects-api]. The optimistic-locking tests define the core contract: missing `If-Match` skips the check, a matching version passes, and a stale version raises `409` with `{"error": "version_conflict", "current_version": <value>}` [@optimistic-tests].

The admin form uses that version boundary for save conflicts, but snapshots are outside the same guard in the current endpoints. That distinction is important when changing [Record CRUD And Publishing](record-crud-and-publishing): ordinary update conflicts are protected by `If-Match`, while restore behavior currently trusts the authorized caller and applies the stored JSON payload directly [@objects-api].
