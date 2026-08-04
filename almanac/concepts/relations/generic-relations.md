---
title: "Generic Relations"
summary: "Generic relations store typed links between records in one relation table, including manual links, schema-derived links, relation metadata, and inverse display labels."
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
  - id: relation-list
    type: file
    path: frontend/portal/src/components/RelationsList.tsx
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
---

Generic relations are Katalon's shared graph table for links between records. A `Relation` row stores `from_type`, `from_id`, `to_type`, `to_id`, a string `relation_type`, JSONB relation metadata, a schema-derived flag, and creation time [@models]. The same table holds direct relations created through the relation API and relations mirrored from schema relation fields, so object, entity, place, occurrence, and procedure links can be queried through one surface [@relation-api] [@relation-service].

## Relation Rows

The relation table does not use foreign keys to every possible record table. Instead, each endpoint is stored as a type string plus UUID pair, with indexes on `(from_type, from_id)` and `(to_type, to_id)` for directional lookup [@models]. This design fits Katalon's multi-type record model because a relation can connect any supported record type pair without adding a join table per pair.

The relation API lists relations with optional endpoint filters, creates manual relations, updates `relation_type` or metadata, and deletes relation rows [@relation-api]. Create, update, and delete operations require admin or editor permission through the route dependency, while listing is a normal read endpoint [@relation-api].

## Schema-Derived Relations

Schema relation fields are stored in record metadata but mirrored into the relation table. `sync_schema_relations` deletes prior schema-derived rows for the source record, loads top-level relation fields and relation sub-fields inside group fields, and creates fresh `Relation` rows from current metadata values [@relation-service]. Mirrored rows set `is_schema_derived` and record their source field in relation metadata, using `group.field` syntax for relation sub-fields inside groups [@relation-service].

This mirror keeps form-oriented metadata and graph-oriented relation queries aligned. A cataloguer can work through a field configured by the [schema engine](../metadata/schema-engine), while portal and workflow code can read from `relations` without re-parsing every record's JSONB metadata.

## Relation Types And Inverse Labels

Relation fields can point at a relation-type vocabulary through `settings.relation_type_vocab` [@schema-screen]. Relation-type vocabularies are ordinary vocabularies with `kind == "relation"`, and vocabulary terms include `inverse_label` JSONB for labels shown from the opposite direction [@models]. The relation itself stores only the relation type code; label resolution happens outside the relation row.

The portal relation list receives a `resolveLabel` callback and passes it the relation type plus direction flag, so the display layer can choose the forward or inverse label for the current record [@relation-list]. The same component computes the other endpoint from the current record ID and navigates to a type-specific portal path [@relation-list].

## Procedure Rule

Generic relations also carry workflow constraints. When creating a relation between a procedure and an object, the relation API checks whether the procedure is an active `loan_out`; if so, it rejects a second active loan-out relation for the same object with HTTP 409 [@relation-api]. The helper that finds active loans joins procedures through the relation table in either direction, which keeps the rule independent of relation direction [@relation-service].

## Related Pages

Read [schema engine](../metadata/schema-engine) for relation field configuration and [vocabularies](../metadata/vocabularies) for relation-type vocabularies and inverse labels.
