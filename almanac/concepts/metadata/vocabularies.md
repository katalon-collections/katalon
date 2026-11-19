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
  - id: skos-import-service
    type: file
    path: backend/src/katalon/services/skos_import_service.py
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
  - id: vocabulary-import-screen
    type: file
    path: frontend/admin/src/components/screens/VocabularyImport.tsx
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: screen-settings
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: vocab-ref-service
    type: file
    path: backend/src/katalon/services/vocabulary_reference_service.py
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

Vocabularies are Katalon's controlled lists for cataloguing values and relation labels. A `Vocabulary` has a unique name, a hierarchy flag, an optional `canonical_uri` (for the concept scheme / namespace), and a `kind` of either `term` or `relation`; each `VocabularyTerm` belongs to one vocabulary, has multilingual labels, optional inverse labels, a canonical concept `uri`, `exact_match_uris` for cross-concordances (`skos:exactMatch`), and JSONB metadata for term-specific custom fields [@models]. Term vocabularies may have a parent-child structure; relation vocabularies are always flat. The authenticated vocabulary API exposes flat term lists, single vocabularies and terms, nested trees, ancestor chains, CRUD operations, and import endpoints, so vocabularies are both user-facing controlled data and configuration used by the [schema engine](schema-engine) [@vocab-api].

Authenticated vocabulary responses include relative `_links`: a vocabulary links to itself, its terms, and its tree; a term links to itself, its vocabulary, ancestors, and its parent when one exists. These are REST navigation links, not stable Linked Open Data identities [@schemas]. The anonymous Portal API resolves terms only through a configured public `vocab` or `vocab_free` schema field, so it never publishes arbitrary vocabularies; callers may restrict that response to referenced `term_ids` for localized record display. The `relation_types` vocabulary remains available through its dedicated anonymous endpoints [@portal-public-api].

## Terms And Hierarchies

Vocabulary terms are stored as rows with `term`, `label`, `inverse_label`, `metadata`, `parent_id`, `uri`, and `exact_match_uris` fields [@models]. The API can return terms as a flat list filtered by text search over `term` and JSON labels, or as a nested tree built from `parent_id` relationships [@vocab-api]. The ancestor endpoint walks the same in-memory term map from a selected term toward its parents, returning the root-to-parent chain [@vocab-api].

The `is_hierarchical` flag controls whether a term vocabulary may carry a hierarchy; the actual structure is represented by `VocabularyTerm.parent_id` [@models]. The Admin vocabulary editor renders hierarchical vocabularies in parent-before-child order, lets editors select a parent or create a direct child, and excludes the term itself and its descendants from a parent choice [@screen-vocab]. Its vocabulary list uses an expand control to reveal the active vocabulary's hierarchy; revealed terms open their editor. Record-form suggestions use the same parent-before-child order and show the selected term's ancestor path without changing the stored label [@screen-vocab] [@screen-form]. CRUD rejects parent links for flat vocabularies, other vocabularies, self-references, and cycles [@vocab-api]. Deleting a term that has children is blocked with `409` unless the caller chooses `reparent=true` (children move up to the deleted term's parent) or `cascade=true` (the whole subtree is deleted); the `ondelete="SET NULL"` foreign key is only a database safety net, not the delete contract [@vocab-api]. Imports validate that referenced parent terms exist in either current database terms or imported data before writing [@import-service]. Relation vocabularies remain flat and reject parent links in CRUD and import requests.

Vocabulary terms can be duplicated from the Admin vocabulary screen via their three-dots action menu. The duplicate endpoint (`POST /v1/vocabularies/terms/{term_id}/duplicate`) clones the term under the same vocabulary and parent, generates a unique term identifier (e.g. `term_copy`), appends `(Kopie)` / `(Copy)` to labels and inverse labels, resets external canonical URIs, and opens the new term in edit mode for immediate adjustment [@vocab-api] [@screen-vocab].

## Clearing And Deleting Whole Vocabularies

Admins can empty or delete an entire vocabulary from the Settings danger zone (`#settings/gefahrenbereich`), next to the schema reset [@screen-settings]. `GET /v1/vocabularies/{id}/reset-summary` reports the term count, the number of active schema fields (`vocab`/`vocab_free` via `settings.vocabulary_id`, `relation` via `settings.relation_type_vocab`) pointing at the vocabulary, and whether it is a system vocabulary [@vocab-api].

- **Clear terms** (`DELETE /v1/vocabularies/{id}/terms`) deletes every term but keeps the vocabulary row, its schema bindings and its `vocabulary_term` custom fields, so it can be re-imported. Record values that referenced the removed terms stay stored and show the "term deleted" badge, the same as a forced single-term delete [@vocab-ref-service].
- **Delete vocabulary** (`DELETE /v1/vocabularies/{id}`) removes the vocabulary and all its terms and soft-deletes its `vocabulary_term` custom fields. If active schema fields still reference it, the request is rejected with `409` (`related_count`) unless `force=true` is passed; with `force` those fields are soft-deleted as well (record data is kept, same as the schema reset) [@vocab-ref-service].
- The system vocabularies `media_types` and `relation_types` are referenced by name in startup seeding, media import and portal endpoints, so they can be cleared but never deleted (`409`) [@vocab-api].

Both actions are admin-only, require typing the vocabulary name in uppercase in the UI, and queue a bulk reindex for affected record types after commit.

## Term And Relation Kinds

The `kind` field separates ordinary controlled terms from relation-type vocabularies [@models]. Schema fields of type `vocab` and `vocab_free` expect a vocabulary with `kind == "term"`, while relation fields can point `settings.relation_type_vocab` at a vocabulary with `kind == "relation"` [@schema-api]. The relation-type sync service scans existing relation rows and adds missing relation type codes as vocabulary terms, preserving existing codes when the default relation-type vocabulary is initialized or refreshed [@relation-type-service].

Inverse labels belong on vocabulary terms. They give relation-type vocabularies a place to store the display label used when a relation is read from the opposite direction [@models]. Relation-type terms can also restrict the record-type pairs they apply to through `applies_from` and `applies_to`; an empty list means unrestricted for that side, and the create/update schema rejects values outside `object`, `entity`, `place`, `occurrence`, and `procedure` [@models] [@schemas].

The terms endpoint can filter by `from_type` and `to_type`, returning terms whose side-specific list is empty or contains the requested record type [@vocab-api]. The Admin vocabulary screen exposes the same contract only for vocabularies with `kind == "relation"` by showing source and target record-type checkbox groups and a compact type-pair summary in the term table [@screen-vocab]. Existing relation terms remain unrestricted after migration because `0029_vocab_term_applies` adds both JSONB columns with `[]` as the non-null server default [@vocab-applies-migration].

This is why relation vocabularies are connected to [generic relations](../relations/generic-relations) rather than being plain dropdown lists.

## Imports

Vocabulary imports can be initiated directly from the vocabulary editor in **Vocabularies** (`ScreenVocab`) via an import modal or in the **Importer** under the **Vocabularies** tab (`VocabularyImport`) [@screen-vocab] [@vocabulary-import-screen]. In addition to flat tabular files (CSV, TSV) and JSON structures, Katalon supports selective SKOS import from standard RDF formats: Turtle (`.ttl`), RDF/XML (`.rdf`, `.xml`), JSON-LD (`.jsonld`), and N-Triples (`.nt`) [@vocab-api] [@skos-import-service].

For SKOS imports, the parser extracts `skos:Concept` nodes, resolves multilingual `skos:prefLabel` values (e.g. `de`, `en`), stores `skos:altLabel` values in term metadata, extracts `skos:exactMatch` concordances into `exact_match_uris`, maps the concept URI into `VocabularyTerm.uri`, and preserves the hierarchical structure (`skos:broader` and inverse `skos:narrower` mapped to `parent_id` when the vocabulary is hierarchical) [@skos-import-service]. SKOS imports support selective scoping: editors can filter by `concept_scheme` URI or `top_concept` URI, limit hierarchy depth (`max_depth`), and cap term count (`max_terms`) to safeguard against memory overflow with massive thesauri [@vocab-api] [@skos-import-service]. Dry-run previews report detected concept schemes and top concepts to facilitate one-click filtering.

CSV and TSV accept mapping from input columns to `term`, `parent_term`, `label:<lang>`, `inverse_label:<lang>`, `uri`, `exact_match_uris`, or `field:<name>` targets; relation vocabularies omit `parent_term`. `field:<name>` fills a custom term field (`vocabulary_term` schema of this vocabulary; types `text`, `number`, `boolean`, `authority`): authority cells take a URL (resolved through `parse_authority_url`, source must match the field) or a bare ID, the label is the term label; repeatable fields split on `|` or `;`. Imported field values pass `validate_metadata` (without required checks); errors are reported per row. JSON and SKOS imports do not map custom fields (SKOS stores only `alt_labels`). JSON can be either a list of term objects or an object with a `terms` list, supporting `uri` and `exact_match_uris` attributes [@vocab-api] [@import-service] [@vocabulary-import-screen]. The import service detects delimiters, tries common encodings, merges duplicate terms by key, supports nested JSON `children`, reports parent conflicts, and supports dry-run statistics before writing [@import-service].
Import writes are keyed by the term code. In append mode the service counts new and updated term codes; in replace mode it deletes existing terms before recreating the imported set when `dry_run` is false [@import-service].

### Import Scenarios And LOD Integration

The vocabulary import pipeline supports three primary integration patterns:

1. **Targeted Subtree Extraction (e.g. Getty AAT / Art & Architecture Thesaurus):** Large general-purpose thesauri contain tens of thousands of concepts across many disciplines. When a cataloguer needs a controlled list for a specific field (such as painting techniques or photographic processes), setting `top_concept` to the root URI (e.g. `http://vocab.getty.edu/aat/300026816` for *oil paint*) extracts only the target concept and its narrower descendants via recursive graph traversal [@skos-import-service]. Hierarchy is preserved via `parent_id` within the selected subset, external concordances (`skos:exactMatch`) are stored in `exact_match_uris`, and the canonical concept URI is persisted in `VocabularyTerm.uri` [@models] [@skos-import-service].
2. **Scheme-Wide Domain Ingestion (e.g. Nomisma, DNB Sachbegriffe):** For domain-specific vocabularies that bundle concepts under a dedicated `skos:ConceptScheme`, filtering by scheme URI extracts all member concepts while filtering out unrelated helper nodes in mixed dumps [@skos-import-service]. Multilingual labels (`skos:prefLabel` across German, English, and other languages) are extracted into `label`, alternative labels (`skos:altLabel`) are preserved in `metadata_["alt_labels"]`, and resource limits (`max_terms`, `max_depth`) safeguard against memory exhaustion [@skos-import-service].
3. **Inhouse Legacy Migration (CSV/TSV/JSON):** Tabular or custom JSON term lists from legacy cataloguing systems are mapped to internal term keys, multilingual labels, and hierarchical parent codes, allowing institutions to normalize existing inventories without requiring prior RDF conversion [@import-service].

## Custom Term Metadata

Vocabulary terms participate in the schema system through `FieldDefinition.target_type == "vocabulary_term"` and store custom values in `VocabularyTerm.metadata_` [@models]. The local decision record explains why this was unified with the existing schema engine: an earlier missing storage path caused imported `external_id` data to disappear, and the chosen fix reused JSONB metadata plus the existing authority field model instead of adding a separate vocabulary-only field system [@vocab-decision].

Term custom fields are intentionally narrower than record fields. The current schema API allows only `text`, `number`, `boolean`, and `authority` for vocabulary terms, which keeps vocabulary metadata useful for authority enrichment without pulling full record-form behavior into term editing [@schema-api].

## LOD Boundary

Vocabularies publish REST JSON, with first-class concept identifiers and alignment fields added in #349: `Vocabulary.canonical_uri` stores the vocabulary namespace or ConceptScheme URI, while `VocabularyTerm.uri` and `VocabularyTerm.exact_match_uris` store the canonical concept URI (e.g. Getty AAT) and external cross-concordances (`skos:exactMatch`) [@models] [@vocab-api]. The vocabulary and term models do not yet carry a per-vocabulary public/private publication flag or complete SKOS RDF serialization (`skos:Concept`, `skos:inScheme`, `skos:broader`). Authority hits can include provider-specific URI data in `extra`, and the reusable authority input writes only `{source, external_id, label}` into field values [@screen-vocab].

Issue #268 and #349 record the minimal Linked Open Data direction: add an explicit publication boundary for vocabularies, mint stable URLs for public vocabularies and terms, return JSON-LD/SKOS for those resources without requiring API tokens, and persist usable authority URIs for match links before considering larger SPARQL, graph UI, CIDOC-CRM, or record-RDF work [@issue-268].


### Search Semantics And Graph Traversal

In Elasticsearch and the REST search API, vocabulary fields index exact display labels and identifiers without recursive ancestor expansion (#362). Fulltext- and facet-expansion over monohierarchical `parent_id` structures was evaluated and deliberately rejected: in standard keyword searches, automatic subtree expansion produces substantial search noise (loss of precision), degrades facet reliability, and conflicts with polyhierarchical SKOS thesauri. Transitive hierarchical reasoning across vocabularies (e.g. finding all artefacts tagged with sub-concepts of *Traffic* via `skos:broader*`, including cross-concordances via `skos:exactMatch`) is designated for the materialized RDF projection in Oxigraph via SPARQL property paths (#364).

## Related Pages

Read [schema engine](schema-engine) for field definitions that point at vocabularies, [authority sources](../integrations/authority-sources) for authority values stored in term metadata, [OAI And Export Mappings](../../architecture/workflows/oai-and-export-mappings) for the current OAI-DC export boundary, and [generic relations](../relations/generic-relations) for relation-type vocabularies.
