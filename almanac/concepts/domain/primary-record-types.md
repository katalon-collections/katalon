---
title: "Primary Record Types"
summary: "Katalon's primary record types separate inventory records from process records while sharing configurable metadata and relation behavior."
topics: [concepts, domain, records, metadata, relations]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: drop-search-vector
    type: file
    path: backend/migrations/versions/0044_drop_search_vector.py
  - id: data-model-doc
    type: file
    path: docs/01_datenmodell.md
  - id: decision
    type: file
    path: .agents/knowledge/decisions/vier-bestandstypen.md
---

Katalon uses four primary inventory record types and one separate process record type. Objects, Entities, Places, and Occurrences are stored in separate tables and share JSONB metadata, status fields, timestamps, and record versions in the current SQLAlchemy model [@models]. Procedures are stored in their own table because they describe loans, acquisition, conservation, and other processes around objects rather than collection entities themselves [@models]. This distinction feeds the [Schema Engine](../metadata/schema-engine), [Generic Relations](../relations/generic-relations), and [Procedures](procedures) pages.

## Four Inventory Families

Objects represent physical or digital artefacts such as photographs, documents, paintings, scans, and born-digital files [@data-model-doc]. In code, `Object` has an `objects` table, an optional unique `idno`, `object_type`, `collection_status`, publication `status`, JSONB `metadata`, timestamps, and a version counter [@models].

Entities represent people and organizations connected to collection records. The `Entity` model stores a unique optional `idno`, an indexed `entity_type`, publication `status`, JSONB metadata, timestamps, and version counter [@models].

Places represent geographic locations. The `Place` model adds a PostGIS `POINT` geometry column with SRID 4326 and a GiST index, while keeping the shared metadata, status, timestamp, and version shape [@models].

Occurrences represent works, events, and abstract concepts. The concept document uses Occurrence for things that are not objects, actors, or places, including exhibitions, campaigns, works, and concepts [@data-model-doc]. The code stores them in `occurrences` with `occurrence_type`, JSONB metadata, status, timestamps, and version [@models].

## Why They Are Separate

The recorded decision for the data model chooses four separate inventory tables instead of one generic intrinsic table. The stated reasons are clearer schema, better query performance, and direct PostGIS use on `places` instead of hiding geometry in a generic attribute system [@decision].

The tables are separate, but they are not isolated silos. The `FieldDefinition` model targets records by `target_type` and optional `target_subtype`, so configurable fields can be scoped to one record family or subtype without schema migrations [@models]. The `Relation` model stores `from_type`, `from_id`, `to_type`, `to_id`, relation type, and JSONB metadata, so records can still be connected across type boundaries [@models].

## Procedure As Fifth Record Family

Procedure is the fifth record family in practice, but it is not a fifth inventory type. Its table has `procedure_type`, status, start, end, and due dates, a reference number, JSONB metadata, timestamps, and version [@models]. The data-model decision explicitly keeps Procedure separate from the four equal inventory tables [@decision].

That separation matters when reading workflows. A Procedure can link to Objects through the same relations infrastructure, but Procedure-specific rules can enforce process constraints such as preventing a second active outgoing loan for the same object. See [Procedures](procedures) for those invariants.

## Shared Metadata And Indexing Shape

All five current record families use JSONB metadata, which lets configured fields live in data instead of table columns while retaining their domain-specific columns [@models].

The searchable read model is Elasticsearch, not a PostgreSQL TSVECTOR column. Migration `0044` removes the unused `search_vector` columns from Objects, Entities, Places, Occurrences, and Procedures, leaving search document construction to the [Search And Indexing](../../architecture/workflows/search-and-indexing) workflow [@drop-search-vector].

The useful mental model is fixed record families plus dynamic fields. Fixed families give the system stable endpoints, storage, relation targets, and workflow rules. Dynamic fields let institutions adapt cataloging detail through the [Schema Engine](../metadata/schema-engine) instead of code changes.
