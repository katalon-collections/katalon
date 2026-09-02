---
title: "Search And Indexing"
summary: "Katalon's search workflow builds Elasticsearch documents from database records, configured schema flags, relation titles, and inherited linked fields."
topics: [architecture, workflows, search, indexing, elasticsearch, visibility]
sources:
  - id: admin-object-list
    type: file
    path: backend/src/katalon/api/v1/objects.py
  - id: admin-procedure-list
    type: file
    path: backend/src/katalon/api/v1/procedures.py
  - id: admin-list-tests
    type: file
    path: backend/tests/integration/test_objects_integration.py
  - id: search-service
    type: file
    path: backend/src/katalon/services/search_service.py
  - id: search-api
    type: file
    path: backend/src/katalon/api/v1/search.py
  - id: topbar
    type: file
    path: frontend/admin/src/components/layout/Topbar.tsx
  - id: admin-search-test
    type: file
    path: backend/tests/test_admin_search.py
  - id: advanced-search-service
    type: file
    path: backend/src/katalon/services/advanced_search_service.py
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
  - id: index-task-tests
    type: file
    path: backend/tests/test_index_tasks.py
---

Katalon's search workflow turns Objects, Entities, Places, Occurrences, and Procedures into Elasticsearch documents that the REST search API, portal search, OAI-PMH, and maintenance jobs can query. The builder uses record metadata, schema flags, relation titles, and configured inherited relation fields. Celery tasks write or rebuild documents in Elasticsearch [@search-service] [@index-tasks]. Anonymous visibility is enforced both in normal record queries and in Elasticsearch search filters, so public search excludes non-public records and inactive collection objects [@visibility] [@visibility-tests].

## Document Shape

`build_index_doc()` is the central builder. It cleans empty metadata keys, extracts a display title from common metadata names such as `title`, `label`, `name`, and German equivalents, falls back to `idno`, and builds `search_text` from fields marked `is_searchable` in `field_definitions` [@search-service]. The builder stores normalized metadata under `metadata`, flattens repeatable values for stable Elasticsearch mapping, and adds core fields such as `record_type`, `title`, `status`, `created_at`, and `updated_at` [@search-service].

Facet data is opt-in. Fields marked `is_facet` are copied into keyword-safe `facet_<field>` fields; numeric facets additionally receive typed `number_facet_<field>` doubles, and group fields are indexed under nested `grp_<field>` keys [@search-service]. The Elasticsearch mapping contains dynamic templates for those prefixes, while the main `metadata` object is stored with `enabled: false`, so search and aggregations depend on explicit extracted fields rather than arbitrary JSON indexing [@elasticsearch].

Public fields marked `is_searchable` also produce typed nested `adv_fields` entries. Text and selection values use text/keyword projections, numbers use doubles, booleans use booleans, and EDTF-lite dates use inclusive integer bounds. Public relation fields produce `adv_relations` entries with source field, target type, target ID, and relation type [@search-service] [@elasticsearch]. Existing indices must be rebuilt after this mapping is introduced.

## Relation Denormalization

The index includes relation titles because search and portal facets need names without joining back to PostgreSQL. `_load_relation_titles()` reads relations in both directions for a record and resolves linked Entity, Place, and Occurrence titles into `related_entities`, `related_places`, and `related_occurrences` arrays [@search-service]. Like the main document builder, it falls back to `idno` when the linked record's `label`-style metadata does not yield a title (for example when `label` is configured as a group field rather than a flat field) — without this fallback the linked record silently drops out of the array even though the relation exists in PostgreSQL [@search-service]. Elasticsearch maps those arrays as keyword fields and always aggregates them for relation facets [@elasticsearch].

Relation fields can inherit selected metadata from linked records. During document building, `build_index_doc()` reads relation-type field definitions, looks for `settings.target_type` and `settings.inherited_fields`, embeds the selected values under `linked_<type>s`, and adds keyword-safe `facet_inherited_<type>_<field>` values for portal filtering [@search-service]. After a record is indexed, `cascade_reindex_task` reindexes records that link to it, so a changed linked record can update documents that inherit its fields at one hop [@index-tasks]. The type-specific and full reindex tasks use the same document builder. This is the runtime side of [Inherited Fields In Elasticsearch](../../decisions/search/inherited-fields-in-elasticsearch).

## Query Execution

`search_documents()` builds a boolean Elasticsearch query. Text search uses `query_string` against boosted `title` and `search_text` fields, appends a trailing wildcard for simple user text, and rejects leading wildcards through Elasticsearch settings [@elasticsearch]. Filters cover record type, status, metadata facet values sent as `meta_` filters, inclusive numeric bounds sent as `range_<field>_from` and `range_<field>_to`, relation facet values, and active-only object visibility for anonymous callers [@elasticsearch].

Advanced search validates every requested field against the current public searchable schema. Direct conditions query `adv_fields`. Relation conditions are resolved from the innermost target outwards: each target search returns public record IDs, then the parent condition filters `adv_relations` by source field and target ID. The public builder permits two relation steps and limits each intermediate ID set to 10,000; broader intermediate results return a validation error instead of issuing an unbounded terms query [@advanced-search-service] [@elasticsearch]. This keeps relation traversal query-time and avoids cascading multi-hop denormalization.

Every search response includes default aggregations for type, status, and the three relation title arrays. Requested configured facets add `meta_<field>` aggregations over the matching `facet_<field>` keyword fields and self-excluding `numeric_<field>` min/max statistics over `number_facet_<field>` [@elasticsearch]. `search_service.search()` converts raw Elasticsearch hits into API items, categorical buckets, and numeric bounds for [Portal Search And Facets](portal-search-and-facets) [@search-service].

The Admin record lists are a separate PostgreSQL query path. Their `q` parameter performs a case-insensitive literal substring match against the record ID and JSON metadata; procedure lists also include the reference number. Thus `axt` matches `Steinaxt` without requiring users to type wildcards, and literal `%` or `_` characters do not broaden the query [@admin-object-list] [@admin-procedure-list] [@admin-list-tests].

The Admin header uses `/v1/search/admin`, a separate admin-only entrypoint, when the logged-in user is an `admin` or `superuser`; lower roles keep the ordinary record-search path [@search-api] [@topbar]. That endpoint keeps Elasticsearch for collection records, then directly queries the small PostgreSQL tables for users, vocabularies and their terms, static pages, OAI sets, schema fields, subtypes, form variants, banners, and configured authority sources [@search-api] [@search-service]. This avoids indexing staff-only data and lets each result navigate to its owning Admin screen. Fixed settings sections stay as a client-side route list because they have no separate database rows [@topbar]. The focused regression test fixes the user-result contract as `kind=user`, `route=users`, and no per-user edit id [@admin-search-test].

## Reindex And Repair Paths

Incremental indexing calls `index_record()`, which builds a document and dispatches `index_record_task` with retries [@search-service] [@index-tasks]. A failed permanent index write records an `index_failed` audit-log entry, which makes indexing failure visible beyond task logs [@index-tasks].

Bulk repair paths are also Celery tasks. `bulk_reindex_type_task` acquires a Redis lock scoped to the record type before reading PostgreSQL and replacing that type's Elasticsearch documents. Concurrent rebuilds of the same type therefore run serially, while different types retain independent locks. The one-hour lock lease bounds abandoned locks after worker failure [@index-tasks] [@index-task-tests]. `reindex_all_task` rebuilds every supported record type after ensuring the index exists. `reconciliation_job_task` compares database and Elasticsearch counts or IDs, queues missing records for reindexing, and removes stale Elasticsearch documents [@index-tasks].

## Visibility Contract

Anonymous record access is limited to `public` or `published` statuses [@visibility]. `collection_status` (e.g. `on_loan_out`, `deaccessioned`) is a curatorial/inventory field driven by procedure completion and is deliberately independent of portal visibility — an object on loan stays visible in the portal as long as its `status` is public.

That visibility rule is an invariant for search consumers. Portal search, object media lookup, and OAI-PMH may differ in response format, but public-facing entrypoints must not expose draft or internal records through the index.
