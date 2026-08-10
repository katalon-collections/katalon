---
title: "Separate Record Tables"
summary: "Katalon stores Objects, Entities, Places, and Occurrences in separate tables while sharing JSONB metadata through the schema engine."
topics: [decisions, data-model, records, metadata, database]
sources:
  - id: decision
    type: file
    path: .agents/knowledge/decisions/vier-bestandstypen.md
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: data-doc
    type: file
    path: docs/01_datenmodell.md
---

Katalon intentionally stores its four primary inventory families in four tables: `objects`, `entities`, `places`, and `occurrences`. The choice rejects one generic records table for the core cataloguing model, while preserving configurable metadata through JSONB columns and `field_definitions` [@decision] [@models]. Future work on records should start from this split because it shapes API surfaces, database indexes, PostGIS usage, and the [Primary Record Types](../../concepts/domain/primary-record-types) concept.

## Context

A single generic records table with many configurable attributes brings high setup complexity [@decision]. The product still needs dynamic metadata, but it also needs clear domain families for artefacts, people and organizations, places, and works or events [@data-doc]. A single generic table would make those families uniform in storage, but it would hide differences that the system already treats as meaningful.

Places are the clearest pressure against a generic table. The current `Place` model has a PostGIS `POINT` geometry column with SRID 4326 and a GiST index, while the other inventory types do not [@models]. That is hard to model cleanly when every record is only a row in one table with all domain detail buried in attributes.

## Decision

The data model uses one table per primary inventory family. `Object` stores object-specific fields such as `object_type` and `collection_status`; `Entity` stores `entity_type`; `Place` stores `place_type` and `geom`; and `Occurrence` stores `occurrence_type` [@models]. All four tables share `status`, JSONB `metadata`, `search_vector`, timestamps, and a version counter [@models].

Configurable fields are not implemented as new columns per institution. The `FieldDefinition` model records `target_type`, optional `target_subtype`, field name, multilingual label, field type, required and repeatable flags, visibility, search flags, sort order, JSONB settings, and group-field parentage [@models]. Record values then live in each table's JSONB metadata column, which connects this decision to the [Schema Engine](../../concepts/metadata/schema-engine).

Procedure is not folded into the four inventory tables. The recorded decision keeps Procedure separate because loans, acquisition, and conservation are process records, not a fifth equal inventory type [@decision]. The current model follows that shape with a `procedures` table that adds process dates and reference number fields while still using JSONB metadata [@models].

## Consequences

The split gives database queries and indexes a stable place to attach type-specific behavior. Place geometry can use PostGIS directly; object media can relate to `objects`; subtype fields can be indexed by their record family; and future rules can apply to one family without checking a generic discriminator for every row [@models].

The cost is that cross-type behavior must be written deliberately. Generic features such as dynamic fields, search indexing, snapshots, audit, and relations must account for each record family rather than assuming one records table. Katalon accepts that cost because the [Generic Relation Model](generic-relation-model) and schema engine provide shared layers where the families must meet.

The durable rule for maintainers is simple: add domain-specific record behavior to the typed table or service for that family, and add shared cataloguing fields through `field_definitions` and JSONB metadata. A new generic records table would reverse this decision and should not be introduced as a local convenience.
