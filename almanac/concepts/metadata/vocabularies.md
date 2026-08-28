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
  - id: portal-public-api
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
  - id: import-service
    type: file
    path: backend/src/katalon/services/vocabulary_import_service.py
  - id: schema-api
    type: file
    path: backend/src/katalon/api/v1/schema_admin.py
  - id: schemas
    type: file
    path: backend/src/katalon/core/schemas.py
  - id: relation-type-service
    type: file
    path: backend/src/katalon/services/relation_type_service.py
  - id: screen-vocab
    type: file
    path: frontend/admin/src/components/screens/ScreenVocab.tsx
  - id: vocab-applies-migration
    type: file
    path: backend/migrations/versions/0029_vocab_term_applies.py
  - id: vocab-decision
    type: file
    path: .agents/knowledge/decisions/vocabulary-custom-fields.md
  - id: issue-268
    type: web
    url: https://github.com/karkraeg/Katalon/issues/268
---

Vocabularies are Katalon's controlled lists for cataloguing values and relation labels. A `Vocabulary` has a unique name, a hierarchy flag, and a `kind` of either `term` or `relation`; each `VocabularyTerm` belongs to one vocabulary, has multilingual labels, optional inverse labels, and JSONB metadata for term-specific custom fields [@models]. Term vocabularies may have a parent-child structure; relation vocabularies are always flat. The authenticated vocabulary API exposes flat term lists, single vocabularies and terms, nested trees, ancestor chains, CRUD operations, and import endpoints, so vocabularies are both user-facing controlled data and configuration used by the [schema engine](schema-engine) [@vocab-api].

Authenticated vocabulary responses include relative `_links`: a vocabulary links to itself, its terms, and its tree; a term links to itself, its vocabulary, ancestors, and its parent when one exists. These are REST navigation links, not stable Linked Open Data identities [@schemas]. The anonymous Portal read model only exposes the `relation_types` vocabulary and its terms, returning the same relative `_links` under `/portal/v1` (self and terms for a vocabulary; self, vocabulary, and parent for a term) [@portal-public-api].

## Terms And Hierarchies

Vocabulary terms are stored as rows with `term`, `label`, `inverse_label`, `metadata`, and `parent_id` fields [@models]. The API can return terms as a flat list filtered by text search over `term` and JSON labels, or as a nested tree built from `parent_id` relationships [@vocab-api]. The ancestor endpoint walks the same in-memory term map from a selected term toward its parents, returning the root-to-parent chain [@vocab-api].

The `is_hierarchical` flag controls whether a term vocabulary may carry a hierarchy; the actual structure is represented by `VocabularyTerm.parent_id` [@models]. The Admin vocabulary editor renders hierarchical vocabularies in parent-before-child order, lets editors select a parent or create a direct child, and excludes the term itself and its descendants from a parent choice [@screen-vocab]. CRUD rejects parent links for flat vocabularies, other vocabularies, self-references, and cycles [@vocab-api]. Deleting a parent promotes its direct children to root terms through the database foreign-key rule, preserving their subtrees [@models]. Imports validate that referenced parent terms exist in either current database terms or imported data before writing [@import-service]. Relation vocabularies remain flat and reject parent links in CRUD and import requests.

## Term And Relation Kinds

The `kind` field separates ordinary controlled terms from relation-type vocabularies [@models]. Schema fields of type `vocab` and `vocab_free` expect a vocabulary with `kind == "term"`, while relation fields can point `settings.relation_type_vocab` at a vocabulary with `kind == "relation"` [@schema-api]. The relation-type sync service scans existing relation rows and adds missing relation type codes as vocabulary terms, preserving existing codes when the default relation-type vocabulary is initialized or refreshed [@relation-type-service].

Inverse labels belong on vocabulary terms. They give relation-type vocabularies a place to store the display label used when a relation is read from the opposite direction [@models]. Relation-type terms can also restrict the record-type pairs they apply to through `applies_from` and `applies_to`; an empty list means unrestricted for that side, and the create/update schema rejects values outside `object`, `entity`, `place`, `occurrence`, and `procedure` [@models] [@schemas].

The terms endpoint can filter by `from_type` and `to_type`, returning terms whose side-specific list is empty or contains the requested record type [@vocab-api]. The Admin vocabulary screen exposes the same contract only for vocabularies with `kind == "relation"` by showing source and target record-type checkbox groups and a compact type-pair summary in the term table [@screen-vocab]. Existing relation terms remain unrestricted after migration because `0029_vocab_term_applies` adds both JSONB columns with `[]` as the non-null server default [@vocab-applies-migration].

This is why relation vocabularies are connected to [generic relations](../relations/generic-relations) rather than being plain dropdown lists.

## Imports

Vocabulary imports accept CSV, TSV, or JSON. CSV and TSV require a JSON mapping from input columns to `term`, `parent_term`, `label:<lang>`, or `inverse_label:<lang>` targets; relation vocabularies omit and reject `parent_term`. JSON can be either a list of term objects or an object with a `terms` list [@vocab-api] [@import-service]. The import service detects delimiters, tries common encodings, merges duplicate terms by key, supports nested JSON `children`, reports parent conflicts, and supports dry-run statistics before writing [@import-service].

Import writes are keyed by the term code. In append mode the service counts new and updated term codes; in replace mode it deletes existing terms before recreating the imported set when `dry_run` is false [@import-service].

## Custom Term Metadata

Vocabulary terms participate in the schema system through `FieldDefinition.target_type == "vocabulary_term"` and store custom values in `VocabularyTerm.metadata_` [@models]. The local decision record explains why this was unified with the existing schema engine: an earlier missing storage path caused imported `external_id` data to disappear, and the chosen fix reused JSONB metadata plus the existing authority field model instead of adding a separate vocabulary-only field system [@vocab-decision].

Term custom fields are intentionally narrower than record fields. The current schema API allows only `text`, `number`, `boolean`, and `authority` for vocabulary terms, which keeps vocabulary metadata useful for authority enrichment without pulling full record-form behavior into term editing [@schema-api].

## LOD Boundary

Vocabularies currently publish REST JSON, not Linked Open Data. The vocabulary and term models do not carry a per-vocabulary public/private publication flag, a stable dereferenceable term URL, or SKOS fields such as `skos:Concept`, `skos:inScheme`, `skos:prefLabel`, `skos:broader`, or `skos:exactMatch` [@models] [@vocab-api]. Authority hits can include provider-specific URI data in `extra`, but the reusable authority input writes only `{source, external_id, label}` into field values, so external authority URIs are not automatically durable term links [@screen-vocab].

Issue #268 records the minimal Linked Open Data direction: add an explicit publication boundary for vocabularies, mint stable URLs for public vocabularies and terms, return JSON-LD/SKOS for those resources, and persist usable authority URIs for match links before considering larger SPARQL, graph UI, CIDOC-CRM, or record-RDF work [@issue-268].

## Related Pages

Read [schema engine](schema-engine) for field definitions that point at vocabularies, [authority sources](../integrations/authority-sources) for authority values stored in term metadata, [OAI And Export Mappings](../../architecture/workflows/oai-and-export-mappings) for the current OAI-DC export boundary, and [generic relations](../relations/generic-relations) for relation-type vocabularies.
