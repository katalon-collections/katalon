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
  - id: portal-public
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
  - id: index-health-api
    type: file
    path: backend/src/katalon/api/v1/index_health.py
  - id: settings-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
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
  - id: reindex-state
    type: file
    path: backend/src/katalon/workers/reindex_state.py
  - id: reindex-tests
    type: file
    path: backend/tests/test_reindex_coordination.py
  - id: index-status
    type: file
    path: backend/src/katalon/api/v1/index_health.py
  - id: collection-service
    type: file
    path: backend/src/katalon/services/collection_service.py
  - id: relations-api
    type: file
    path: backend/src/katalon/api/v1/relations.py
  - id: storage-location-service
    type: file
    path: backend/src/katalon/services/storage_location_service.py
  - id: storage-locations-api
    type: file
    path: backend/src/katalon/api/v1/storage_locations.py
---

Katalon's search workflow turns inventory and process records, including Collections, into Elasticsearch documents that the REST search API, portal search, OAI-PMH, and maintenance jobs can query. The builder uses record metadata, schema flags, relation titles, and configured inherited relation fields. Celery tasks write or rebuild documents in Elasticsearch [@search-service] [@index-tasks]. Anonymous visibility is enforced both in normal record queries and in Elasticsearch search filters, so public search excludes non-public records and inactive collection objects [@visibility] [@visibility-tests].

## Document Shape

`build_index_doc()` is the central builder. It cleans empty metadata keys, extracts a display title from common metadata names such as `title`, `label`, `name`, and German equivalents, falls back to `idno`, and builds `search_text` from fields marked `is_searchable` in `field_definitions` [@search-service]. Before building, `normalize_url_values()` brings every URL value — top-level and inside groups — into the shape `{value[, label]}` and drops empty ones; group instances are kept in the document as nested `grp_*` objects, so one plain-string URL next to an object used to make Elasticsearch reject the whole document [@search-service]. The `group_fields` dynamic template now maps `grp_*` as `nested` with `dynamic: false`: sub-fields are stored in `_source` but not indexed, because nothing queries them (the advanced search uses `adv_fields`) and a dynamically guessed sub-field type (for example `long` after a number, then "640 KB") rejected the whole record. The template only applies to indices created after the change, so `release-meta.toml` marks 1.49.0 `reindex_required`. Until a full reindex has replaced an old index, `index_document` and `bulk_index_documents` re-send a record that was rejected with a parsing error without its `grp_*` keys (logged as a warning) instead of losing it [@search-service]. The builder stores normalized metadata under `metadata`, flattens repeatable values for stable Elasticsearch mapping, and adds core fields such as `record_type`, `title`, `status`, `created_at`, and `updated_at` [@search-service].

Facet data covers every public field. Each public metadata field is copied into a keyword-safe `facet_all_<field>` field; number fields additionally receive typed `number_facet_all_<field>` doubles, and group fields are indexed under nested `grp_<field>` keys [@search-service]. For simple field facets, `is_facet` only gates which fields public search endpoints aggregate, so toggling it needs no reindex. Derived date buckets, vocabulary paths and relation facets have their own materialized projections; changing their source settings can require a reindex. The Elasticsearch mapping contains dynamic templates for those prefixes, while the main `metadata` object is stored with `enabled: false`, so search and aggregations depend on explicit extracted fields rather than arbitrary JSON indexing [@elasticsearch].

Public fields marked `is_searchable` also produce typed nested `adv_fields` entries. Text and selection values use text/keyword projections, numbers use doubles, booleans use booleans, and EDTF-lite dates use inclusive integer bounds. Public relation fields produce `adv_relations` entries with source field, target type, target ID, and relation type. Outgoing free relations from the `relations` table to public objects, entities, places, and occurrences produce entries with an empty source field, the relation type, and `direction: outgoing`; they are collected in the same pass that loads related titles, so a target that is not public is never indexed. Incoming relations are deliberately not indexed on the target: a record can be the target of tens of thousands of relations, and Elasticsearch rejects documents with more than 10,000 nested entries (a reindex failed on exactly that). Outgoing entries are additionally capped at 5,000 per record with a warning [@search-service] [@elasticsearch]. Existing indices must be rebuilt after the mapping or this projection changes.

## Relation Denormalization

The index includes relation titles because search and portal facets need names without joining back to PostgreSQL. `_load_relation_titles()` reads relations in both directions for a record and resolves linked Entity, Place, and Occurrence titles into `related_entities`, `related_places`, and `related_occurrences` arrays [@search-service]. Like the main document builder, it falls back to `idno` when the linked record's `label`-style metadata does not yield a title (for example when `label` is configured as a group field rather than a flat field) — without this fallback the linked record silently drops out of the array even though the relation exists in PostgreSQL [@search-service]. Elasticsearch maps those arrays as keyword fields and always aggregates them for relation facets [@elasticsearch].

Relation fields can inherit selected metadata from linked records. During document building, `build_index_doc()` reads relation-type field definitions, looks for `settings.target_type` and `settings.inherited_fields`, embeds the selected values under `linked_<type>s`, and adds keyword-safe `facet_inherited_<type>_<field>` values for portal filtering [@search-service]. After a record is indexed, `cascade_reindex_task` reindexes records linked in either direction, so title, subtype and visibility changes refresh incoming and outgoing relation facets as well as inherited fields at one hop. Each counterpart is rebuilt once; self-links and soft-deleted counterparts are skipped [@index-tasks]. The type-specific and full reindex tasks use the same document builder. This is the runtime side of [Inherited Fields In Elasticsearch](../../decisions/search/inherited-fields-in-elasticsearch).

## Query Execution

`search_documents()` builds a boolean Elasticsearch query. Text search uses `query_string` against boosted `title` and `search_text` fields, appends a trailing wildcard for simple user text, and rejects leading wildcards through Elasticsearch settings. Elasticsearch-rejected query syntax is returned by the API as HTTP 422 rather than an internal error. Filters cover record type, status, metadata facet values sent as `meta_` filters, inclusive numeric bounds sent as `range_<field>_from` and `range_<field>_to`, relation facet values, and active-only object visibility for anonymous callers [@elasticsearch].

Result ordering follows an explicit `sort` parameter (`idno_asc`, `title_asc`, `newest`, `oldest`) mapped to a fixed `SORT_CLAUSES` table; an unrecognized or absent value leaves Elasticsearch's default `_score` ordering in place [@elasticsearch]. An empty query (`q` unset) still runs as `match_all`, which assigns every hit the same constant score — without a tiebreaker, "relevance" ordering would then depend on arbitrary Lucene segment order. `search_documents()` special-cases this: when `query` is falsy and no explicit sort was requested, it forces `idno_asc` so the empty-query "Relevance" option returns a deterministic order instead [@elasticsearch] [@visibility-tests].

### Deep Pagination

`search_documents()` serves `from`/`size` requests directly up to `FORWARD_LIMIT` (10,000, matching Elasticsearch's default `index.max_result_window`). Beyond that depth, a request with a deterministic sort (an explicit `sort` value, or the forced `idno_asc` fallback for an empty query) is instead served from the tail: a size-0 pilot query gets the exact `total`, then the actual page is fetched with the sort clauses reversed and `reverse_from = total − from − size`, and the returned hits are reversed back into normal order before the response is built [@elasticsearch]. This keeps first and last pages at O(page_size) cost regardless of collection size; there is no depth ceiling for either end with a deterministic sort. A request that lands in neither the cheap front nor the cheap back (near the middle of a result set larger than `2 × FORWARD_LIMIT`) raises `ValueError`, which the `/v1/search` endpoint turns into HTTP 416 [@search-api] [@elasticsearch]. Relevance-ranked queries (free-text `query` set, no explicit sort) have no reversible order — `_score`-only sort lacks a stable tiebreaker across shards — so they keep the flat `FORWARD_LIMIT` and also return 416 past it, with a message pointing callers at a fixed sort or a narrower query [@elasticsearch]. The portal's page-jump input and numbered buttons check these windows before navigating and keep the current results visible when the target is unreachable; see [Portal Search And Facets](portal-search-and-facets).

Advanced search validates every requested field against the current public searchable schema. Direct conditions query `adv_fields`. Relation conditions are resolved from the innermost target outwards: each target search returns public record IDs, then the parent condition filters `adv_relations` by source field and target ID. The public builder permits two relation steps and limits each intermediate ID set to 10,000; broader intermediate results return a validation error instead of issuing an unbounded terms query [@advanced-search-service] [@elasticsearch]. This keeps relation traversal query-time and avoids cascading multi-hop denormalization. A `relation_type` condition does the same for free relations: it names relation type, direction, and target type instead of a field. For `outgoing` it filters `adv_relations` by those plus the resolved target IDs. For `incoming` it searches the source records with the nested conditions and collects, by a nested terms aggregation over their outgoing entries, the IDs of the searched type they point to (bounded like other intermediate sets), then filters by `ids`. While such a search loads, the portal says it searches across relations and adds a hint after 1.5 seconds. `GET /portal/v1/search/advanced/relation-types?record_type=` lists the free relation types usable for a record type: outgoing ones from its own documents, incoming ones from other types' outgoing entries that point to it (nested aggregations with `reverse_nested` record counts), so the builder only offers conditions that can match. Selection-like fields (`vocab`, `vocab_free`, `authority`, `pid`, `url`) also accept `in`/`not_in` with 1–50 values, which covers an OR over values inside an otherwise all-matching group [@advanced-search-service] [@portal-public].

Every search response includes default aggregations for type, status, and the three relation title arrays. Requested configured facets add `meta_<field>` aggregations over the matching `facet_all_<field>` keyword fields and self-excluding `numeric_<field>` min/max statistics over `number_facet_all_<field>`; the inherited relation facets are the exception and keep aggregating their legacy top-level `facet_inherited_<type>_<field>` fields [@elasticsearch]. `search_service.search()` converts raw Elasticsearch hits into API items, categorical buckets, and numeric bounds for [Portal Search And Facets](portal-search-and-facets) [@search-service].

### Hierarchical Filtering (Collections And Storage Locations)

To avoid multi-hop denormalization cascades in Elasticsearch, hierarchical filtering expands hierarchy filters at query time before handing record IDs or titles to the existing query path.

When portal or admin search filters by `rel_collection`, the API resolves the requested collection title, ID number, or UUID against `collections`, walks descendant subcollections through the `parent_id` tree, and passes matching titles and ID numbers as a `terms` filter to Elasticsearch [@search-api] [@collection-service]. The `/relations` endpoint separately accepts `include_subcollections=true`; that path uses `get_collection_subtree_ids()` and its recursive CTE to retrieve relations targeting a collection or any of its subcollections, allowing collection detail pages to display holdings from descendant branches without duplicate relational links [@relations-api] [@collection-service].

Storage location hierarchies (`storage_locations.parent_id`) remain internal logistics data and are strictly excluded from public portal search. Instead, `GET /v1/storage-locations/{id}/objects` and `GET /v1/objects?storage_location_id={id}&include_sublocations=true` resolve the storage location subtree via `get_storage_location_subtree_ids()` and join against the `relations` table [@storage-location-service] [@storage-locations-api] [@admin-object-list].

Vocabulary term hierarchies (`vocabulary_terms.parent_id`) are intentionally excluded from Elasticsearch query expansion to avoid precision loss and polyhierarchy conflicts in keyword search (#362); transitive semantic traversal across broader/narrower concepts is delegated to the materialized RDF projection in Oxigraph via SPARQL property paths (`skos:broader*`) (#364).

The Admin record lists are a separate PostgreSQL query path. Their `q` parameter performs a case-insensitive literal substring match against the record ID and JSON metadata; procedure lists also include the reference number. Thus `axt` matches `Steinaxt` without requiring users to type wildcards, and literal `%` or `_` characters do not broaden the query [@admin-object-list] [@admin-procedure-list] [@admin-list-tests].

The Admin header uses `/v1/search/admin`, a separate admin-only entrypoint, when the logged-in user is an `admin` or `superuser`; lower roles keep the ordinary record-search path [@search-api] [@topbar]. That endpoint keeps Elasticsearch for collection records, then directly queries the small PostgreSQL tables for users, vocabularies and their terms, static pages, OAI sets, schema fields, subtypes, form variants, banners, and configured authority sources [@search-api] [@search-service]. This avoids indexing staff-only data and lets each result navigate to its owning Admin screen. Fixed settings sections stay as a client-side route list because they have no separate database rows [@topbar]. The focused regression test fixes the user-result contract as `kind=user`, `route=users`, and no per-user edit id [@admin-search-test].

## Reindex And Repair Paths

Incremental indexing calls `index_record()`, which builds a document and defers `index_record_task` via `after_commit()`, dispatching it only after the transaction durably commits (#392) [@search-service] [@index-tasks]. A failed permanent index write records an `index_failed` audit-log entry, which makes indexing failure visible beyond task logs [@index-tasks].

Bulk repair paths are also Celery tasks. Every rebuild request — schema changes, vocabulary label changes, imports, the manual "reindex type" action — goes through `request_bulk_reindex()`, which coalesces per type: it marks the type `dirty` and enqueues a job only if none is already waiting (`queued` marker) [@reindex-state]. `bulk_reindex_type_task` takes a non-blocking Redis run lock with a two-minute lease that a watchdog thread renews while the job is alive; a second job for the same type returns `deferred` immediately instead of occupying a worker thread. A job that finishes while the type is `dirty` again requests exactly one follow-up, so any burst of changes yields at most one running and one following rebuild per type. Locks held by a worker are released on `worker_shutdown`; after a crash the lease expires within two minutes [@index-tasks] [@reindex-tests]. Both rebuild tasks ack their message on start (`acks_late=False`), because Redis redelivers unacked messages after its one-hour visibility timeout and would start a long rebuild twice. Crash recovery instead relies on the `dirty` marker: it carries a token, is removed only after a successful run if no new request arrived meanwhile, and `worker_ready` re-requests every type that is still dirty but neither running nor queued. A failed run does not trigger its own follow-up, so a persistent error (e.g. Elasticsearch down) cannot loop.

The rebuild streams: it snapshots the type's record IDs, builds documents batch by batch (`REINDEX_BATCH_SIZE`, concurrent build sessions per batch) and overwrites them in Elasticsearch by ID, so only one batch is held in memory and the portal keeps serving each record's previous document until the new one lands. Afterwards documents of the type that were not rebuilt are removed — after re-checking them against PostgreSQL, so a record created during the run is not dropped [@index-tasks] [@elasticsearch]. Progress (total, built, indexed, start, end, error) is written to Redis and exposed as `GET /v1/admin/index-status` with an ETA; a run whose progress says "running" while its lease is gone is reported as `failed` [@index-status]. Several field definitions can be changed in one transaction via `PUT /v1/schema/{target_type}/bulk`, which requests at most one rebuild; the Admin facet settings screen uses it.

Each Celery task runs its coroutine in a fresh `asyncio.run` loop and creates its own NullPool engine; workers never use the API's pooled global engine, whose connections are bound to the loop that opened them. `ES_INDEX_NAME` (`katalon_records`) is an alias onto a dated physical index (`<name>_<timestamp>_<random>`); every read and write uses the alias name. `reindex_all_task` (`POST /v1/search/reindex`, coalesced like type rebuilds) is the full rebuild: it creates a fresh physical index, streams every type into it, then switches the alias atomically and deletes the previous index — the only way to replace a mapping that a dynamic field got wrong, which the in-place type rebuild cannot. While it runs, `index_document`/`delete_document` also write to the new index (its name sits in Redis under `katalon:reindex:shadow:<name>`), and a catch-up pass re-reads every record with `updated_at`/`deleted_at` after the build started. A build failure before the alias switch deletes the half-built index and leaves the alias untouched. Once the switch is attempted, its target is retained even when the response is lost: Elasticsearch may already have switched. Failure to delete a previous index is logged and leaves that old index for later operator cleanup, without failing the completed switch or deleting the live target. Installations from before this change have a concrete index under the alias name; the first full rebuild removes it in the same atomic alias request (`remove_index` + `add`). All rebuilds — per type and full — share one run lock (`katalon:reindex:run`), so they never run in parallel; a deferred one is resubmitted when the running one ends. `GET /v1/admin/index-status` reports the full rebuild separately (`full_rebuild`, with `current_type`). `reconciliation_job_task` compares database and Elasticsearch counts or IDs, queues missing records for reindexing, and removes stale Elasticsearch documents [@index-tasks].

Portal search includes Occurrences in its public type set, and the Admin settings screen offers both `occurrence` reindexing and an index-health widget that compares database and Elasticsearch counts per record type [@portal-public] [@settings-screen] [@index-health-api]. When a public work is visible on its detail route but missing from portal search, the durable diagnosis starts with the worker and Elasticsearch index state, then the `occurrence` count delta and a type-specific reindex; media upload behavior is a separate object-only workflow [@portal-public] [@index-health-api] [@settings-screen]. See [Media And IIIF](media-and-iiif) for that boundary.

## Visibility Contract

Anonymous record access is limited to `public` or `published` statuses [@visibility]. `collection_status` (e.g. `on_loan_out`, `deaccessioned`) is a curatorial/inventory field driven by procedure completion and is deliberately independent of portal visibility — an object on loan stays visible in the portal as long as its `status` is public.

That visibility rule is an invariant for search consumers. Portal search, object media lookup, and OAI-PMH may differ in response format, but public-facing entrypoints must not expose draft or internal records through the index.
