---
title: "Cross-Cutting Record Contract"
summary: "The architectural contract enforcing feature capabilities and subsystem registries across all seven core record types."
topics: [architecture, data-model, records, contract, testing]
sources:
  - id: schemas
    type: file
    path: backend/src/katalon/core/schemas.py
  - id: contract-test
    type: file
    path: backend/tests/test_record_type_contract.py
  - id: batch-service
    type: file
    path: backend/src/katalon/services/batch_service.py
  - id: purge-tasks
    type: file
    path: backend/src/katalon/workers/purge_tasks.py
  - id: audit-service
    type: file
    path: backend/src/katalon/services/audit_service.py
  - id: relation-service
    type: file
    path: backend/src/katalon/services/relation_service.py
  - id: export-service
    type: file
    path: backend/src/katalon/services/export_service.py
---

Katalon operates on seven distinct record types (`RECORD_TYPES`): `object`, `entity`, `place`, `occurrence`, `procedure`, `collection`, and `storage_location` [@schemas]. Rather than a single polymorphic table, each type possesses an independent database table, optimistic concurrency locking (`version`), timestamps, and dynamic JSONB metadata governed by the schema engine.

To maintain architectural coherence and prevent subsystem drift, all cross-cutting features must explicitly account for all seven types or define an intentional, documented exclusion [@contract-test].

## The Seven Core Record Types

1. **`object`** (`objects` table): Physical and digital collection artifacts (photos, documents, paintings, 3D assets).
2. **`entity`** (`entities` table): Persons, families, and corporate bodies/organizations.
3. **`place`** (`places` table): Geographic locations with PostGIS point geometry.
4. **`occurrence`** (`occurrences` table): Works (FRBR/LRMoo), historical events, exhibitions, and conceptual topics.
5. **`collection`** (`collections` table): Archival fonds, series, and curated collections with self-referential `parent_id` hierarchy.
6. **`storage_location`** (`storage_locations` table): Physical locations (building, room, shelf, box) with self-referential `parent_id` hierarchy. Internal logistics and security-sensitive data.
7. **`procedure`** (`procedures` table): Workflow and process records (loans, acquisitions, deaccessions, conservation).

## Cross-Cutting Capability Matrix

Not every subsystem applies identically to every type, but deviations are deliberate and codified in `CAPABILITY_MATRIX` within `test_record_type_contract.py` [@contract-test]:

| Capability | Supported Record Types | Intentional Exclusions & Rationale |
|---|---|---|
| `core_schemas` | All 7 types | None. Canonical source in `core.schemas.RECORD_TYPES`. |
| `batch_edit` | All 7 types | `storage_location` supports field ops and relation ops; `set_status` raises `ValueError` because storage locations have no status lifecycle. |
| `batch_subtype` | All 7 types | Each type defines its subtype column key (e.g. `storage_location_type`). |
| `relation_service` | All 7 types | All 7 types can be endpoints of generic relations. |
| `working_set` | All 7 types | Working sets can curate batches of any of the 7 types. |
| `idno_preview` | All 7 types | Previewing sequential/custom identifiers works across all types. |
| `index_health` | All 7 types | ES vs. DB count reconciliation verifies health for all 7 types. |
| `reconciliation` | All 7 types | Full-text and index re-sync sweeps encompass all 7 types. |
| `cascade_reindex` | All 7 types | Relation updates trigger reindexing across all 7 types. |
| `relation_cleanup`| All 7 types | Referential cleanup upon record deletion inspects all 7 types. |
| `json_csv_export` | All 7 types | Streaming JSON and CSV exports support all 7 types. |
| `audit_logging` | All 7 types | `audit_service._LOGGABLE_RECORD_TYPES` tracks audits for all 7 types. |
| `searchable_visibility` | All 7 types | Cross-type search visibility checking includes all 7 types. |
| `soft_delete_purge` | 6 types (`CORE_TYPES - {"procedure"}`) | `procedure` has no `deleted_at` column; it uses an archival lifecycle (`archive()`) rather than soft deletion and retention-window purging. |
| `portal_public_visibility` | 5 types (`CORE_TYPES - {"procedure", "storage_location"}`) | `procedure` (internal workflows) and `storage_location` (security-sensitive location data / theft protection) are strictly internal-only and never published to the portal. |

## Subsystem Registries in Code

Each subsystem defines an explicit map or set of record types. The contract test asserts each against the capability matrix:

- `katalon.core.schemas.RECORD_TYPES`: Tuple of all 7 core type names.
- `katalon.services.batch_service._MODEL_MAP`: ORM model mapping for batch operations [@batch-service].
- `katalon.services.batch_service._SUBTYPE_KEY`: Subtype attribute names [@batch-service].
- `katalon.services.relation_service._RECORD_MODELS`: ORM models for relation endpoints [@relation-service].
- `katalon.services.working_set_service._RECORD_MODELS`: Models eligible for working set items.
- `katalon.api.v1.index_health._MODEL_MAP`: Models verified in index health checks.
- `katalon.workers.index_tasks._record_models()`: Models indexed into Elasticsearch.
- `katalon.services.export_service.RECORD_MODELS`: Models and subtype attributes for data export [@export-service].
- `katalon.services.audit_service._LOGGABLE_RECORD_TYPES`: Record types that record audit log history [@audit-service].
- `katalon.core.visibility.SEARCHABLE_RECORD_TYPES`: Record types visible to authenticated search.
- `katalon.workers.purge_tasks._PURGEABLE_MODELS`: Models participating in retention-window purge sweeps [@purge-tasks].
- `katalon.api.v1.portal_public._PUBLIC_TYPES`: Types exposed to unauthenticated public portal visitors.

## Automated Enforcement

The test `backend/tests/test_record_type_contract.py` executes in CI to enforce this contract. If a new record type is added or a subsystem dictionary is modified without considering all seven types, `test_core_record_type_capability_contract` immediately fails, pointing directly to the missing registry.
