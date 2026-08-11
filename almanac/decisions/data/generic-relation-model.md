---
title: "Generic Relation Model"
summary: "Katalon uses one typed relation table with metadata and vocabulary-governed relation types for links across record families."
topics: [decisions, data-model, relations, vocabularies, records]
sources:
  - id: decision
    type: file
    path: .agents/knowledge/decisions/relationen-design.md
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: relation-type-service
    type: file
    path: backend/src/katalon/services/relation_type_service.py
  - id: relation-api
    type: file
    path: backend/src/katalon/api/v1/relations.py
  - id: vocab-api
    type: file
    path: backend/src/katalon/api/v1/vocabularies.py
  - id: data-doc
    type: file
    path: docs/01_datenmodell.md
---

Katalon's relation model is generic: one `relations` table stores typed edges between records, and relation meaning is governed by relation-type vocabularies rather than by a different join table for every pair of record types. A relation row carries source and target type/UUID pairs, a `relation_type` code, JSONB metadata, and a schema-derived marker [@models]. This model lets the [Primary Record Types](../../concepts/domain/primary-record-types) stay separate while [Generic Relations](../../concepts/relations/generic-relations) connect them.

## Context

GLAM data needs links across objects, people, organizations, places, works, events, and concepts. The data model documentation gives examples such as Object to Entity for a photographer, Object to Place for a photographed location, Object to Occurrence for an exemplar of a work, Entity to Entity for membership, and Occurrence to Place for an event location [@data-doc].

The recorded decision compares a field-gated relation model with a flexibility-first model. Field-gated relations would allow links only where a field configuration explicitly permitted them, while the chosen model allows relation fields throughout forms and shifts governance to configurable relation-type vocabularies [@decision].

## Decision

Katalon uses one relation table. The `Relation` model stores `from_type`, `from_id`, `to_type`, `to_id`, `relation_type`, JSONB `metadata`, `is_schema_derived`, and `created_at`, with indexes on the source and target endpoint pairs [@models]. Endpoint references are type strings plus UUIDs instead of normal foreign keys to one fixed target table, because the model must connect multiple record families.

Relation type governance uses vocabularies. The decision records `target_type`, optional `target_subtype`, and `relation_type_vocab` as the relation field settings that constrain form behavior [@decision]. In the current model, vocabularies have a `kind` field and vocabulary terms have multilingual labels plus `inverse_label`, so relation-type vocabularies can display different labels depending on direction [@models]. Relation-type terms can also carry `applies_from` and `applies_to` record-type lists; the vocabulary endpoint filters selectable terms by those lists, and the relation API validates create/update requests through the shared relation-type service before writing [@models] [@vocab-api] [@relation-api] [@relation-type-service]. See [Vocabularies](../../concepts/metadata/vocabularies) for the controlled-list side of this design.

Existing raw relation type codes are not thrown away when relation vocabularies are introduced. `sync_relation_type_terms` reads distinct `Relation.relation_type` values, compares them with existing terms in a vocabulary, and creates missing `VocabularyTerm` rows with simple German and English labels [@relation-type-service]. That keeps historical relation data usable while moving display and governance toward vocabulary terms.

## Consequences

The model maximizes cross-record flexibility. Any supported source type can point at any supported target type without adding a pair-specific table, and relation metadata can store role, date range, or other edge-specific facts on the link itself [@models] [@data-doc].

The tradeoff is semantic discipline. Because the database table accepts string type names and string relation codes, correctness depends on service validation, form settings, and well-maintained relation-type vocabularies rather than on a dense network of foreign-key tables. Pair-specific relation-type applicability is enforced in services and API behavior, not as pair-specific database tables or foreign keys [@relation-api] [@relation-type-service]. The recorded decision explicitly accepts that governance shift because hard field gates would block common GLAM linking patterns [@decision].

Maintainers should avoid adding special-purpose relation tables unless a new workflow has constraints that cannot be expressed as a typed relation plus metadata. Even then, the generic table remains the graph surface other code expects.
