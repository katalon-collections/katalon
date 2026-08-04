---
title: "Record Subtypes"
summary: "Record subtypes classify the four primary record types and let schema fields target all records of a type or only one configured subtype."
topics: [concepts, metadata, records, schema]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: subtype-api
    type: file
    path: backend/src/katalon/api/v1/record_subtypes.py
  - id: subtype-service
    type: file
    path: backend/src/katalon/services/subtype_service.py
  - id: schema-service
    type: file
    path: backend/src/katalon/services/schema_service.py
  - id: schema-api
    type: file
    path: backend/src/katalon/api/v1/schema_admin.py
  - id: subtype-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSubtype.tsx
  - id: migration
    type: file
    path: backend/migrations/versions/0013_record_subtypes_and_missing_type_columns.py
  - id: main
    type: file
    path: backend/src/katalon/main.py
---

Record subtypes are configured labels and internal names under Katalon's four primary record types: object, entity, place, and occurrence. The `record_subtypes` table stores the subtype name, multilingual label, sort order, and default flag per primary type, while the primary record tables store their selected subtype in `object_type`, `entity_type`, `place_type`, or `occurrence_type` [@models]. The schema engine uses those subtype names to decide whether a field applies globally to a primary type or only to one subtype, so subtypes are a metadata-scope mechanism as well as a cataloguing classification [@subtype-service].

## Data Model

`RecordSubtype` rows are unique by `(primary_type, name)` [@models]. The migration that introduced the table also added `object_type` and `place_type` columns, making object and place subtype storage match the existing entity and occurrence type columns in the ORM model [@migration] [@models]. Procedures are not managed through `record_subtypes`; they have their own fixed `procedure_type` values in schema validation [@schema-api].

Katalon creates default subtype rows at startup for object `objekt`, entity `person`, place `geographikum`, and occurrence `werk` when those rows are missing [@main]. These defaults give every primary type at least one browseable subtype without hard-coding a field schema for that subtype.

## Admin Lifecycle

The record subtype API lists subtypes, optionally filtered by primary type, and allows admins to create, update, or delete subtype definitions [@subtype-api]. It normalizes non-empty names, rejects unknown primary types, enforces uniqueness, and unsets other defaults for the same primary type when a subtype is marked default [@subtype-api]. Deletion is blocked when records of that primary type still use the subtype name, because `subtype_has_assigned_records` counts assigned rows through the relevant type column [@subtype-service].

The admin subtype screen exposes tabs for objects, entities, places, and occurrences, then edits internal name, German and English labels, sort order, and default status [@subtype-screen]. Existing subtype internal names are disabled in the UI after creation, which matches the database's use of names as stable scope keys for records and schema fields [@subtype-screen].

## Schema Targeting

Field definitions can carry an optional `target_subtype` [@models]. When the schema service loads fields for a record type and subtype, it returns fields whose `target_subtype` is `NULL` together with fields that exactly match the requested subtype [@schema-service]. This lets one schema define shared fields for all objects while adding subtype-only fields for a narrower cataloguing case.

The schema API verifies that a non-null subtype exists before creating or updating a top-level field for primary record types [@schema-api]. That validation is important because stored metadata lives in JSONB and would otherwise accept orphaned field scopes with no corresponding record classification.

## Related Pages

Read [schema engine](schema-engine) for how subtype-scoped fields are loaded and validated. Subtype-specific relation fields still enter the same relation graph described in [generic relations](../relations/generic-relations).
