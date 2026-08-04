---
title: "Search And Indexing"
summary: "Katalon's search workflow builds Elasticsearch documents from database records, configured schema flags, relation titles, and inherited linked fields."
topics: [architecture, workflows, search, indexing, elasticsearch, visibility]
sources:
  - id: search-service
    type: file
    path: backend/src/katalon/services/search_service.py
  - id: elasticsearch
    type: file
    path: backend/src/katalon/integrations/elasticsearch.py
  - id: index-tasks
    type: file
    path: backend/src/katalon/workers/index_tasks.py
  - id: visibility
    type: file
    path: backend/src/katalon/core/visibility.py
  - id: visibility-tests
    type: file
    path: backend/tests/test_search_visibility.py
---

Katalon's search workflow turns Objects, Entities, Places, Occurrences, and Procedures into Elasticsearch documents that the REST search API, portal search, OAI-PMH, and maintenance jobs can query. The builder uses record metadata, schema flags, and relation titles; it also has a linked-record path for inherited relation fields, but current Admin-saved relation settings use `target_type` while the builder reads `relation_target_type` [@search-service]. Celery tasks write or rebuild documents in Elasticsearch [@index-tasks]. Anonymous visibility is enforced both in normal record queries and in Elasticsearch search filters, so public search excludes non-public records and inactive collection objects [@visibility] [@visibility-tests].

## Document Shape

`build_index_doc()` is the central builder. It cleans empty metadata keys, extracts a display title from common metadata names such as `title`, `label`, `name`, and German equivalents, falls back to `idno`, and builds `search_text` from fields marked `is_searchable` in `field_definitions` [@search-service]. The builder stores normalized metadata under `metadata`, flattens repeatable values for stable Elasticsearch mapping, and adds core fields such as `record_type`, `title`, `status`, `created_at`, and `updated_at` [@search-service].

Facet data is opt-in. Fields marked `is_facet` are copied into keyword-safe `facet_<field>` fields, and group fields are indexed under nested `grp_<field>` keys [@search-service]. The Elasticsearch mapping contains dynamic templates for those two prefixes, while the main `metadata` object is stored with `enabled: false`, so search and aggregations depend on explicit extracted fields rather than arbitrary JSON indexing [@elasticsearch].

## Relation Denormalization

The index includes relation titles because search and portal facets need names without joining back to PostgreSQL. `_load_relation_titles()` reads relations in both directions for a record and resolves linked Entity, Place, and Occurrence titles into `related_entities`, `related_places`, and `related_occurrences` arrays [@search-service]. Elasticsearch maps those arrays as keyword fields and always aggregates them for relation facets [@elasticsearch].

Relation fields can also inherit selected metadata from linked records once schema settings and indexer settings use the same target-type key. During document building, `build_index_doc()` reads relation-type field definitions, looks for `settings.inherited_fields` and `settings.relation_target_type`, and embeds the selected values under `linked_<type>s` entries when that config is present [@search-service]. After a record is indexed, `cascade_reindex_task` reindexes records that link to it, so a changed linked record can update documents that inherit its fields at one hop [@index-tasks]. This is the runtime side of [Inherited Fields In Elasticsearch](../../decisions/search/inherited-fields-in-elasticsearch).

## Query Execution

`search_documents()` builds a boolean Elasticsearch query. Text search uses `query_string` against boosted `title` and `search_text` fields, appends a trailing wildcard for simple user text, and rejects leading wildcards through Elasticsearch settings [@elasticsearch]. Filters cover record type, status, metadata facet values sent as `meta_` filters, relation facet values, and active-only object visibility for anonymous callers [@elasticsearch].

Every search response includes default aggregations for type, status, and the three relation title arrays. Requested configured facets add `meta_<field>` aggregations over the matching `facet_<field>` keyword fields [@elasticsearch]. `search_service.search()` converts raw Elasticsearch hits into API items and aggregation buckets for [Portal Search And Facets](portal-search-and-facets) [@search-service].

## Reindex And Repair Paths

Incremental indexing calls `index_record()`, which builds a document and dispatches `index_record_task` with retries [@search-service] [@index-tasks]. A failed permanent index write records an `index_failed` audit-log entry, which makes indexing failure visible beyond task logs [@index-tasks].

Bulk repair paths are also Celery tasks. `bulk_reindex_type_task` deletes all documents for one record type and rebuilds them, while `reindex_all_task` rebuilds every supported record type after ensuring the index exists [@index-tasks]. `reconciliation_job_task` compares database and Elasticsearch counts or IDs, queues missing records for reindexing, and removes stale Elasticsearch documents [@index-tasks].

## Visibility Contract

Anonymous record access is limited to `public` or `published` statuses, and collection objects must also have `collection_status == "active"` [@visibility]. Search adds the same active-object rule when there is no current user, and a test asserts that anonymous search includes both the public status filter and the active collection-status condition [@visibility-tests].

That visibility rule is an invariant for search consumers. Portal search, object media lookup, and OAI-PMH may differ in response format, but public-facing entrypoints must not expose draft records or inactive collection objects through the index.
