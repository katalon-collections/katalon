---
title: "Storage Locations"
summary: "Katalon models physical storage locations as a sixth primary type with parent_id hierarchy, and links Objects to them through the existing generic relations table instead of a direct foreign key."
topics: [decisions, data-model, records, relations, spectrum]
sources:
  - id: decision
    type: file
    path: .agents/knowledge/decisions/standortverwaltung.md
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: relation-decision
    type: file
    path: almanac/decisions/data/generic-relation-model.md
  - id: storage-locations-delete-api
    type: file
    path: backend/src/katalon/api/v1/storage_locations.py
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/standortverwaltung.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/standortverwaltung.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Katalon models physical storage locations (house, room, shelf, box, arbitrary depth) as an internal logistics record type within the current seven core types, `StorageLocation`, structurally identical to [Separate Record Tables](separate-record-tables)' `Collection`: a self-referential `parent_id` hierarchy, no PostGIS geometry [@models]. The link from an `Object` to its storage location runs through the existing [Generic Relation Model](generic-relation-model) rather than a direct foreign key [@decision].

## Context

GitHub issue #26 tracked storage-location management as a deliberately excluded scope item, because SPECTRUM (the UK museum collections management standard) treats object location as more than a static field. SPECTRUM's "Location and Movement Control" procedure distinguishes a *normal location* (an object's home storage spot) from a *current location* (which may differ while an object is on loan, on exhibition, or in conservation), and requires a traceable movement history rather than a value that gets silently overwritten on each move.

## Decision

`StorageLocation` gets its own table (`storage_locations`): `id`, a required unique `idno`, `storage_location_type`, self-referential `parent_id` (`ondelete=SET NULL`, arbitrary hierarchy depth), JSONB `metadata` driven by the schema engine's `field_definitions`, timestamps, and an optimistic-locking `version` column [@models]. Unlike the other primary record types, it has no `status` column — storage locations are never portal-visible or public-search-indexed (see below), so draft/internal/public workflow states would have been vestigial; the `idno` is always mandatory (unless an admin-configured idno auto-numbering schema generates it), instead of being conditionally required by draft status. It deliberately does not carry PostGIS geometry — indoor hierarchic containment (building → room → shelf → box) is modeled well enough by `parent_id` alone, and a point/polygon on a shelf record would add complexity without a corresponding use case.

The `ondelete=SET NULL` foreign key is a database-level safety net only, not the deletion contract editors see: `DELETE /v1/storage-locations/{id}` blocks by default (409, with a `child_count`) when the target still has active direct children, so a location is never silently orphaned into a root node. Callers must opt explicitly into either `cascade=true` (soft-delete the whole subtree in one call, guarded by the same relations-in-use check applied across every ID in the subtree) or `reparent=true` (move direct children up to the deleted location's own parent, `None` if it was itself a root) [@storage-locations-delete-api]. Collections and vocabulary terms — the codebase's other two self-referential `parent_id` hierarchies — carry the identical guard/cascade/reparent contract for consistency.

The Object↔StorageLocation link uses the existing generic `relations` table instead of a `location_id` foreign key on `Object`. Two relation-type vocabulary terms, `normal_location` and `current_location`, are seeded with `applies_from=["object"]` and `applies_to=["storage_location"]`, following the same pattern as other relation-type constraints [@relation-decision] [@decision]. Assignment stays a free, generically editable relation — it is not gated behind the Procedure (loans/conservation) workflow — but the object edit form surfaces it through a dedicated "Zugeordnete Lagerorte" sidebar card (same visual tier as Media, Versions, Audit Log, and Linked Procedures) instead of the catch-all "Weitere Beziehungen" list, so catalogers do not have to hunt for it among unrelated free relations. The card, and its underlying relation-type options, only render once at least one `StorageLocation` exists in the system; institutions that never configure storage locations see no trace of the feature on the object form. A location's movement history over time is simply the sequence of relation rows created, edited, and deleted for an object, which is already covered by the existing relation audit trail.

`storage_location` joins the record-type registries needed for the schema engine, subtypes, and relation audit logging, but is deliberately excluded from every registry that gates public visibility: it does not appear in the portal's browsable types, the public search type set, or the bulk importer's valid types. Physical storage location is treated as internal, security-sensitive collection-management data (theft protection), never exposed through the public portal.

## Consequences

Reusing the generic relations table avoids adding a second pair-specific table purely to capture movement history — multiple relation rows already give an auditable timeline for free, consistent with the discipline the generic relation model already asks of maintainers [@relation-decision]. The tradeoff is that "current location" is not a single indexed column: reading an object's current location means querying its `current_location` relations rather than a fast direct join, which is acceptable because storage-location lookups are a low-volume, admin-only operation, not a hot query path like search or portal browsing.


Transitive hierarchy queries (e.g. finding all objects in a building including all rooms, racks, and boxes) are resolved at query time via recursive CTEs in PostgreSQL rather than materialized or denormalized trees. The dedicated endpoint `GET /v1/storage-locations/{id}/objects` and the object list filter `GET /v1/objects?storage_location_id={id}&include_sublocations=true` join the expanded subtree IDs against the generic `relations` table, and the Admin storage location editor (`ScreenStorageLocation`) embeds this object view with a sublocation toggle.
Because `storage_location` never joins the public-facing type registries, any future work that exposes new record types to the portal or public search must explicitly re-evaluate whether storage locations belong there — the default, and the standing decision, is no.
