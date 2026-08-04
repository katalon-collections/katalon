---
title: "Vocabularies"
summary: "Vocabularies define controlled term lists and relation-type lists, with hierarchical terms, inverse labels, import support, and schema-driven custom fields for term metadata."
topics: [concepts, metadata, vocabularies, authority]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: vocab-api
    type: file
    path: backend/src/katalon/api/v1/vocabularies.py
  - id: import-service
    type: file
    path: backend/src/katalon/services/vocabulary_import_service.py
  - id: schema-api
    type: file
    path: backend/src/katalon/api/v1/schema_admin.py
  - id: relation-type-service
    type: file
    path: backend/src/katalon/services/relation_type_service.py
  - id: vocab-decision
    type: file
    path: .agents/knowledge/decisions/vocabulary-custom-fields.md
---

Vocabularies are Katalon's controlled lists for cataloguing values and relation labels. A `Vocabulary` has a unique name, a hierarchy flag, and a `kind` of either `term` or `relation`; each `VocabularyTerm` belongs to one vocabulary, has multilingual labels, optional inverse labels, optional parent-child structure, and JSONB metadata for term-specific custom fields [@models]. The vocabulary API exposes flat term lists, nested trees, ancestor chains, CRUD operations, and import endpoints, so vocabularies are both user-facing controlled data and configuration used by the [schema engine](schema-engine) [@vocab-api].

## Terms And Hierarchies

Vocabulary terms are stored as rows with `term`, `label`, `inverse_label`, `metadata`, and `parent_id` fields [@models]. The API can return terms as a flat list filtered by text search over `term` and JSON labels, or as a nested tree built from `parent_id` relationships [@vocab-api]. The ancestor endpoint walks the same in-memory term map from a selected term toward its parents, returning the root-to-parent chain [@vocab-api].

The `is_hierarchical` flag records whether a vocabulary is intended as a hierarchy, but the actual hierarchy is represented by `VocabularyTerm.parent_id` [@models]. Parent links are set by direct term editing and by import, and the import service validates that referenced parent terms exist in either current database terms or imported data before writing [@import-service].

## Term And Relation Kinds

The `kind` field separates ordinary controlled terms from relation-type vocabularies [@models]. Schema fields of type `vocab` and `vocab_free` expect a vocabulary with `kind == "term"`, while relation fields can point `settings.relation_type_vocab` at a vocabulary with `kind == "relation"` [@schema-api]. The relation-type sync service scans existing relation rows and adds missing relation type codes as vocabulary terms, preserving existing codes when the default relation-type vocabulary is initialized or refreshed [@relation-type-service].

Inverse labels belong on vocabulary terms. They give relation-type vocabularies a place to store the display label used when a relation is read from the opposite direction [@models]. This is why relation vocabularies are connected to [generic relations](../relations/generic-relations) rather than being plain dropdown lists.

## Imports

Vocabulary imports accept CSV, TSV, or JSON. CSV and TSV require a JSON mapping from input columns to `term`, `parent_term`, `label:<lang>`, or `inverse_label:<lang>` targets; JSON can be either a list of term objects or an object with a `terms` list [@vocab-api] [@import-service]. The import service detects delimiters, tries common encodings, merges duplicate terms by key, supports nested JSON `children`, reports parent conflicts, and supports dry-run statistics before writing [@import-service].

Import writes are keyed by the term code. In append mode the service counts new and updated term codes; in replace mode it deletes existing terms before recreating the imported set when `dry_run` is false [@import-service].

## Custom Term Metadata

Vocabulary terms participate in the schema system through `FieldDefinition.target_type == "vocabulary_term"` and store custom values in `VocabularyTerm.metadata_` [@models]. The local decision record explains why this was unified with the existing schema engine: an earlier missing storage path caused imported `external_id` data to disappear, and the chosen fix reused JSONB metadata plus the existing authority field model instead of adding a separate vocabulary-only field system [@vocab-decision].

Term custom fields are intentionally narrower than record fields. The current schema API allows only `text`, `number`, `boolean`, and `authority` for vocabulary terms, which keeps vocabulary metadata useful for authority enrichment without pulling full record-form behavior into term editing [@schema-api].

## Related Pages

Read [schema engine](schema-engine) for field definitions that point at vocabularies, [authority sources](../integrations/authority-sources) for authority values stored in term metadata, and [generic relations](../relations/generic-relations) for relation-type vocabularies.
