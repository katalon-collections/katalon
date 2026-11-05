---
title: "Record Subtypes"
summary: "Record subtypes classify Katalon's record types, let schema fields target all records of a type or only one configured subtype, and can carry authority concepts for export."
topics: [concepts, metadata, records, schema, authority]
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
  - id: normdaten-migration
    type: file
    path: backend/migrations/versions/0075_record_subtype_normdaten.py
  - id: main
    type: file
    path: backend/src/katalon/main.py
  - id: seed-demo
    type: file
    path: backend/scripts/seed_demo.py
  - id: mapping-service
    type: file
    path: backend/src/katalon/services/metadata_mapping_service.py
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

Record subtypes are configured labels and internal names under Katalon's primary record types: object, entity, place, occurrence, procedure, collection, and storage_location. The `record_subtypes` table stores the subtype name, multilingual label, sort order, and default flag per primary type, while the record tables store their selected subtype in `object_type`, `entity_type`, `place_type`, `occurrence_type`, `procedure_type`, `collection_type`, or `storage_location_type` [@models]. The schema engine uses those subtype names to decide whether a field applies globally to a primary type or only to one subtype, so subtypes are a metadata-scope mechanism as well as a cataloguing classification [@subtype-service].

## Data Model

`RecordSubtype` rows are unique by `(primary_type, name)` and carry multilingual labels plus an optional plain-text description of their intended use [@models] [@migration]. The migration that introduced the table also added `object_type` and `place_type` columns, making object and place subtype storage match the existing entity and occurrence type columns in the ORM model [@models]. Migration `0034_procedure_record_subtypes.py` seeds the six built-in Procedure types as `RecordSubtype` rows, while retaining the `procedure_type` column as the selected subtype [@procedure-migration] [@models].

Subtypes can also carry optional authority linking fields: `concept_source`, `concept_id`, `concept_uri`, and `concept_label`, plus `concept_alternatives` (`[{source, id, uri, label, lang}]`, e.g. AAT next to a preferred GND concept; LIDO emits them as alternative `conceptID`/`term`) [@models] [@normdaten-migration]. The subtype API keeps stored alternatives when an update omits the field. The admin subtype screen edits them below a set authority link (authority lookup per source plus language); it stores source, ID and label, and the export derives the canonical URI from source and ID. The same applies to the main concept: the screen stores display URLs (e.g. `wikidata.org/wiki/…`) in `concept_uri`, so the LIDO builder prefers the URI built from `concept_source` + `concept_id`. The demo seed fills Getty AAT data for the nine object subtypes, including `gemaelde` (`300033618`), `druckgrafik` (`300041273`), `fotografie` (`300046300`), and the generic `sammlungsobjekt` fallback (`300191086`); rerunning the seed updates existing object subtype rows as well as newly inserted ones [@seed-demo]. LIDO mappings that choose the record subtype as `objectWorkType` require every configured object subtype to have either a concept id or concept URI before publishing, so a label-only subtype cannot silently produce a weak LIDO work-type export [@mapping-service].

No subtype is created automatically for the primary inventory types (object, entity, place, occurrence, collection, storage_location) during application startup [@main]. Procedure starts with six seeded defaults. A record without a configured subtype stores `NULL` in its type column and uses the primary-type schema only. Once subtypes are configured, new admin forms require a selection, including draft creation. A single configured subtype is preselected; with several subtypes the configured default is used, otherwise the user must choose. The selection is visible in the form and determines the initial schema. If subtype configuration cannot be loaded, saving is disabled rather than treating the failed request as an empty configuration. Existing records keep their stored subtype, including an empty value; the API draft contract is unchanged [@screen-form].

The admin subtype screen exposes tabs for objects, entities, places, occurrences, procedures, collections, and storage locations, then edits internal name, German and English labels, description, sort order, default status, placeholder image URL, and optional authority concept fields [@subtype-screen]. When creating a subtype the internal name is a required field pre-filled from the label by slugifying it (`Person` → `person`, Umlauts transliterated) and stays editable until the subtype is saved; after creation the name is disabled in the UI, which matches the database's use of names as stable scope keys for records and schema fields [@subtype-screen].

The record subtype API lists subtypes, optionally filtered by primary type, and allows admins to create, update, or delete subtype definitions [@subtype-api]. Listing requires `manage_content`, while mutations remain admin-only. The ID-number suggestion used by new-record forms also requires `manage_content`, so catalogers can load both inputs needed for quick creation [@subtype-api] [@idno-api] [@dependencies]. The subtype API normalizes non-empty names, rejects unknown primary types, enforces uniqueness, stores placeholder and authority concept fields, and unsets other defaults for the same primary type when a subtype is marked default [@subtype-api]. Deletion is blocked when records of that primary type still use the subtype name, because `subtype_has_assigned_records` counts assigned rows through the relevant type column; otherwise deletion retires subtype-scoped fields and form variants, including their role defaults [@subtype-service] [@subtype-api].

## Schema Targeting

Field definitions can carry an optional `target_subtype` [@models]. When the schema service loads fields for a record type and subtype, it returns fields whose `target_subtype` is `NULL` together with fields that exactly match the requested subtype [@schema-service]. This lets one schema define shared fields for all objects while adding subtype-only fields for a narrower cataloguing case.

The schema API verifies that a non-null subtype exists before creating or updating a top-level field for primary record types [@schema-api]. That validation is important because stored metadata lives in JSONB and would otherwise accept orphaned field scopes with no corresponding record classification.

An existing top-level field can be moved to another subtype (or to "all") only while no active record holds a value for it. A group moves together with its sub-fields in one transaction. Record values stay in `metadata_` under the field name, so a move of a used field would hide them from records of the old subtype; the API rejects it with `409` and points to duplicating the field in the target subtype and deleting the original [@schema-api].

## Relation Search And Quick Creation

A relation field's optional `target_subtype` narrows target searches through the corresponding object, entity, place, or occurrence list filter. The same subtype is preselected and locked in the quick-create form [@screen-form] [@admin-client]. Without a fixed subtype, the form selects the configured default or the only available subtype. When several subtypes exist without a default, quick creation requires the user to choose one before saving the draft [@screen-form].

The general relationships panel does not constrain the subtype. Users choose it in the target form, including for Procedures [@screen-form]. Record lists expose a subtype filter only when subtypes are configured; selecting one also loads its subtype-specific list columns.

## Related Pages

Read [schema engine](schema-engine) for how subtype-scoped fields are loaded and validated. Subtype-specific relation fields still enter the same relation graph described in [generic relations](../relations/generic-relations).
