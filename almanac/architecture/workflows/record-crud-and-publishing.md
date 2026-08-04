---
title: "Record CRUD And Publishing"
summary: "Katalon record endpoints share a CRUD pattern for primary records and add publication validation, guarded deletes, relation cleanup, search indexing, and procedure completion."
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
  - id: delete-tests
    type: file
    path: backend/tests/test_delete_409.py
---

Record CRUD in Katalon is implemented as five endpoint families: objects, entities, places, occurrences, and procedures. The four public collection types share the same lifecycle: list with filters, create, read with visibility checks, update with optimistic locking, publish, delete, snapshot, restore, and per-record audit log [@objects-api] [@entities-api] [@places-api] [@occurrences-api]. Procedures use the same create/read/update/delete/snapshot/audit shape but replace publishing with domain-specific completion and procedure-state validation [@procedures-api].

## Shared Record Pattern

List endpoints return a page object with `total`, `page`, `page_size`, and `items`, filter by status and subtype where available, apply public visibility for collection record types, and search through `search_vector.match(q)` when a query is supplied [@objects-api] [@entities-api] [@places-api] [@occurrences-api]. Procedure lists are not public-visibility filtered and add procedure type, due date, reference number, status, and full-text filters [@procedures-api].

Create endpoints resolve or validate `idno`, normalize the subtype field, prepare metadata through the schema service, validate metadata with required fields skipped for drafts, and reject duplicate identifiers [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@procedures-api]. Object records additionally validate `collection_status`; places translate latitude and longitude into a PostGIS point; procedures validate a fixed set of procedure types and statuses [@objects-api] [@places-api] [@procedures-api].

Update endpoints retrieve the row, call `check_version` against `If-Match`, repeat identifier and metadata validation, capture old values, mutate scalars and `metadata_`, increment `version`, synchronize schema-defined relations, write an audit-log update entry, and attempt to re-index the record [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@procedures-api]. The form-side conflict resolution described in [Schema Driven Record Forms](schema-driven-record-forms) depends on that `409` version-conflict behavior.

## Publishing

Only objects, entities, places, and occurrences have `/publish` endpoints [@objects-api] [@entities-api] [@places-api] [@occurrences-api]. Each endpoint calls `can_publish`, raises `422` with validation errors when the record cannot be published, then calls `publish_record` and commits [@objects-api] [@publish-service].

`can_publish` checks that the record type is one of the four collection models, that the row exists, that `idno` is present, and that metadata passes schema validation without skipping required fields [@publish-service]. `publish_record` sets `status` to `public`, writes a `publish` audit entry with `changed_fields={"status": "public"}`, and re-indexes the record [@publish-service]. Procedures are excluded from the publish service model map, so their lifecycle is handled by status updates and completion instead [@publish-service] [@procedures-api].

## Guarded Delete

Every delete endpoint requires an editor-or-admin user, checks whether the record exists, counts generic relations for that record, and returns `409` with `related_count` when relations exist and `force=true` was not supplied [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@procedures-api]. The tests assert that delete routes require authentication, that `force=true` does not bypass authentication, and that object/entity relation conflicts return the expected `409` body shape [@delete-tests].

When forced, delete endpoints remove generic relations first, write a delete audit entry, delete the record, attempt to remove it from search, and enqueue `cleanup_relation_refs` for schema-embedded relation references [@objects-api] [@entities-api] [@places-api] [@occurrences-api] [@procedures-api]. This makes the explicit generic relation table the first cleanup boundary, with asynchronous cleanup for metadata references after deletion [@objects-api].

## Procedure Completion

Procedures add a domain operation at `POST /v1/procedures/{id}/complete` [@procedures-api]. The endpoint sets the procedure status to `completed`, optionally updates every linked object's `collection_status`, writes audit entries for each changed object and the procedure, and re-indexes the affected records [@procedures-api].

Procedure validation prevents unknown procedure types or statuses and rejects activation of a `loan_out` procedure when a linked object already has another active outgoing loan [@procedures-api]. That check makes loan-out status more than a label: activating it enforces a collection-management invariant across procedure-object relations [@procedures-api].

Audit entries and snapshots created by these endpoints are explained in [Audit And Snapshots](audit-and-snapshots).
