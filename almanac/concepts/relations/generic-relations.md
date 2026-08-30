---
title: "Generic Relations"
summary: "Generic relations store typed links between records in one relation table; schema fields maintain structured edges while the relationship card adds free extras."
topics: [concepts, relations, records, metadata]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: relation-service
    type: file
    path: backend/src/katalon/services/relation_service.py
  - id: relation-api
    type: file
    path: backend/src/katalon/api/v1/relations.py
  - id: relation-type-service
    type: file
    path: backend/src/katalon/services/relation_type_service.py
  - id: vocab-api
    type: file
    path: backend/src/katalon/api/v1/vocabularies.py
  - id: relation-list
    type: file
    path: frontend/portal/src/components/RelationsList.tsx
  - id: related-objects
    type: file
    path: frontend/portal/src/components/RelatedObjects.tsx
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: admin-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: dependencies
    type: file
    path: backend/src/katalon/core/dependencies.py
---

Generic relations are Katalon's shared graph table for links between records. A `Relation` row stores `from_type`, `from_id`, `to_type`, `to_id`, a string `relation_type`, JSONB relation metadata, a schema-derived flag, and creation time [@models]. The same table holds direct relations created through the relation API and relations mirrored from schema relation fields, so object, entity, place, occurrence, and procedure links can be queried through one surface [@relation-api] [@relation-service].

## Relation Rows

The relation table does not use foreign keys to every possible record table. Instead, each endpoint is stored as a type string plus UUID pair, with indexes on `(from_type, from_id)` and `(to_type, to_id)` for directional lookup [@models]. This design fits Katalon's multi-type record model because a relation can connect any supported record type pair without adding a join table per pair.

The relation API lists relations with optional endpoint filters, creates manual relations, updates `relation_type` or metadata, and deletes relation rows [@relation-api]. Create, update, and delete operations require the `manage_content` capability, which is assigned to catalogers, editors, admins, and superusers. Listing is a normal read endpoint [@relation-api] [@dependencies].

## Admin Picker And Inline Creation

The relationships card on every saved record is the complete, bidirectional graph overview. It groups field-bound edges separately and directs their editing back to the matching schema field. Its add action is for free relationships to other primary record types, including the source record's own type. After choosing the target type, the user chooses a relation type and either selects a search result or opens the schema-driven quick-create dialog [@screen-form]. An exact duplicate of target id and relation type is rejected in the form, while another relation type to the same target remains valid [@screen-form]. Viewers do not see the create action; the create and relation endpoints enforce the same restriction on the server [@screen-form] [@relation-api] [@dependencies].

Quick creation first saves the target as a draft through its ordinary record endpoint. The relationships panel then creates the relation row immediately. If that second request fails, the new draft remains selected and the picker offers `Erneut verknüpfen` instead of deleting the draft [@screen-form] [@admin-client].

## Schema-Derived Relations

Schema relation fields are stored in record metadata but mirrored into the relation table. `sync_schema_relations` deletes prior schema-derived rows for the source record, loads top-level relation fields and relation sub-fields inside group fields, and creates fresh `Relation` rows from current metadata values [@relation-service]. Mirrored rows set `is_schema_derived` and record their source field in relation metadata, using `group.field` syntax for relation sub-fields inside groups [@relation-service].

This mirror keeps form-oriented metadata and graph-oriented relation queries aligned. A cataloguer can work through a field configured by the [schema engine](../metadata/schema-engine), while portal and workflow code can read from `relations` without re-parsing every record's JSONB metadata.

This also defines the save boundary for inline creation. A schema relation field keeps the selected draft in the source form's local metadata until the source record is saved and `sync_schema_relations` runs. This quick-create action is also available inside a quick-create form for every primary target type. The general relationships panel works on an already saved source record and writes its relation row immediately [@screen-form] [@relation-service].

## Relation Types And Inverse Labels

Relation fields can point at a relation-type vocabulary through `settings.relation_type_vocab` and can optionally select one fixed term from it [@schema-screen]. A fixed type makes the field the unambiguous editor for that semantic relationship; without one, the form offers the vocabulary choices. Relation-type vocabularies are ordinary vocabularies with `kind == "relation"`, and vocabulary terms include `inverse_label` JSONB for labels shown from the opposite direction [@models]. The relation itself stores only the relation type code; label resolution happens outside the relation row.

Relation-type vocabularies are always flat: their terms cannot have parent links. They can narrow a term to allowed source and target record types with `VocabularyTerm.applies_from` and `VocabularyTerm.applies_to`, where an empty list means unrestricted for that side [@models]. The vocabulary terms endpoint applies the same rule when called with `from_type` and `to_type`, and the relation API validates create and update requests against relation vocabulary terms before writing the row [@vocab-api] [@relation-api] [@relation-type-service]. If no relation vocabulary term exists for a relation type, the service treats that code as unrestricted, preserving legacy free-text relation types and imported relation rows [@relation-type-service].

The Admin relation picker passes the current source record type and chosen target type into the vocabulary endpoint before showing relation-type choices [@screen-form] [@admin-client]. That keeps the dropdown from offering known-disallowed relation types, while the server remains the final authority and returns HTTP 422 for a relation vocabulary term that does not apply to the requested pair [@relation-api] [@relation-type-service].

The portal relation list receives a `resolveLabel` callback and passes it the relation type plus direction flag, so the display layer can choose the forward or inverse label for the current record [@relation-list]. The same component computes the other endpoint from the current record ID and navigates to a type-specific portal path [@relation-list].

Entity, place, and occurrence pages show linked objects as cards. When those cards use more than one relation type, the portal offers local relation-type chips; they filter the already loaded cards without another API request, and resolve each chip's directional label with the same vocabulary data [@related-objects].

## Procedure Rule

Generic relations also carry workflow constraints. When creating a relation between a procedure and an object, the relation API checks whether the procedure is an active `loan_out`; if so, it rejects a second active loan-out relation for the same object with HTTP 409 [@relation-api]. The helper that finds active loans joins procedures through the relation table in either direction, which keeps the rule independent of relation direction [@relation-service].

## Related Pages

Read [schema engine](../metadata/schema-engine) for relation field configuration and [vocabularies](../metadata/vocabularies) for relation-type vocabularies and inverse labels.
