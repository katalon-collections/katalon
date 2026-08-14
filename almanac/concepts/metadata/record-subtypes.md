---
title: "Record Subtypes"
summary: "Record subtypes classify Katalon's record types and let schema fields target all records of a type or only one configured subtype."
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
    path: backend/migrations/versions/0035_record_subtype_description.py
  - id: procedure-migration
    type: file
    path: backend/migrations/versions/0034_procedure_record_subtypes.py
  - id: main
    type: file
    path: backend/src/katalon/main.py
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: admin-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: idno-api
    type: file
    path: backend/src/katalon/api/v1/idno.py
  - id: dependencies
    type: file
    path: backend/src/katalon/core/dependencies.py
---

Record subtypes are configured labels and internal names under Katalon's four primary record types and Procedures: object, entity, place, occurrence, and procedure. The `record_subtypes` table stores the subtype name, multilingual label, sort order, and default flag per primary type, while the record tables store their selected subtype in `object_type`, `entity_type`, `place_type`, `occurrence_type`, or `procedure_type` [@models]. The schema engine uses those subtype names to decide whether a field applies globally to a primary type or only to one subtype, so subtypes are a metadata-scope mechanism as well as a cataloguing classification [@subtype-service].

## Data Model

`RecordSubtype` rows are unique by `(primary_type, name)` and carry multilingual labels plus an optional plain-text description of their intended use [@models] [@migration]. The migration that introduced the table also added `object_type` and `place_type` columns, making object and place subtype storage match the existing entity and occurrence type columns in the ORM model [@models]. Migration `0034_procedure_record_subtypes.py` seeds the six built-in Procedure types as `RecordSubtype` rows, while retaining the `procedure_type` column as the selected subtype [@procedure-migration] [@models].

No subtype is created automatically for the four inventory primary types during application startup [@main]. Procedure starts with six seeded defaults. A record without a configured subtype stores `NULL` in its type column and uses the primary-type schema only. Once subtypes are configured, new records must select one (except drafts), so subtype-specific fields have an explicit scope.

## Admin Lifecycle

The record subtype API lists subtypes, optionally filtered by primary type, and allows admins to create, update, or delete subtype definitions [@subtype-api]. Listing requires `manage_content`, while mutations remain admin-only. The ID-number suggestion used by new-record forms also requires `manage_content`, so catalogers can load both inputs needed for quick creation [@subtype-api] [@idno-api] [@dependencies]. The subtype API normalizes non-empty names, rejects unknown primary types, enforces uniqueness, and unsets other defaults for the same primary type when a subtype is marked default [@subtype-api]. Deletion is blocked when records of that primary type still use the subtype name, because `subtype_has_assigned_records` counts assigned rows through the relevant type column [@subtype-service].

The admin subtype screen exposes tabs for objects, entities, places, occurrences, and procedures, then edits internal name, German and English labels, description, sort order, and default status [@subtype-screen]. Existing subtype internal names are disabled in the UI after creation, which matches the database's use of names as stable scope keys for records and schema fields [@subtype-screen]. Any unused Procedure subtype, including a seeded default, can be deleted. Deletion is blocked while records use it and otherwise retires its subtype-scoped fields and form variants, including their role defaults [@subtype-api] [@subtype-service].

## Schema Targeting

Field definitions can carry an optional `target_subtype` [@models]. When the schema service loads fields for a record type and subtype, it returns fields whose `target_subtype` is `NULL` together with fields that exactly match the requested subtype [@schema-service]. This lets one schema define shared fields for all objects while adding subtype-only fields for a narrower cataloguing case.

The schema API verifies that a non-null subtype exists before creating or updating a top-level field for primary record types [@schema-api]. That validation is important because stored metadata lives in JSONB and would otherwise accept orphaned field scopes with no corresponding record classification.

## Relation Search And Quick Creation

A relation field's optional `target_subtype` narrows target searches through the corresponding object, entity, place, or occurrence list filter. The same subtype is preselected and locked in the quick-create form [@screen-form] [@admin-client]. Without a fixed subtype, the form selects the configured default when present. Entity quick creation requires a valid configured subtype if no default exists [@screen-form].

The general relationships panel does not constrain the subtype. Users choose it in the target form, including for Procedures [@screen-form]. Record lists expose a subtype filter only when subtypes are configured; selecting one also loads its subtype-specific list columns.

## Related Pages

Read [schema engine](schema-engine) for how subtype-scoped fields are loaded and validated. Subtype-specific relation fields still enter the same relation graph described in [generic relations](../relations/generic-relations).
