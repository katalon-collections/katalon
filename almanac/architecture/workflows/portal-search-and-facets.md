---
title: "Portal Search And Facets"
summary: "Portal search turns URL state into `/v1/search` queries with text, record type, metadata facets, relation facets, pagination, and detail navigation."
topics: [architecture, workflows, search, portal, facets, frontend]
sources:
  - id: search-api
    type: file
    path: backend/src/katalon/api/v1/search.py
  - id: search-page
    type: file
    path: frontend/portal/src/pages/SearchPage.tsx
  - id: portal-client
    type: file
    path: frontend/portal/src/api/client.ts
  - id: settings-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: portal-api
    type: file
    path: backend/src/katalon/api/v1/portal.py
---

Portal search is the public-facing consumer of Katalon's Elasticsearch workflow. The React page stores query text, type filters, metadata facets, relation facets, and page number in the URL, asks `/v1/search` for matching records, and renders links to the record detail routes [@search-page]. The backend search endpoint normalizes those parameters into one search-service call and defaults anonymous requests to public records when no status is supplied [@search-api]. The indexed data and aggregation behavior are explained in [Search And Indexing](search-and-indexing).

## URL State And Backend Parameters

`SearchPage` reads `q`, `type`, `status`, `page`, `meta_*`, `rel_entity`, `rel_place`, and `rel_occurrence` from `useSearchParams()` [@search-page]. It turns those values into a request to `/v1/search`, including `page_size=20` and a comma-separated `facets` list when configured metadata facet fields are available [@search-page].

The backend endpoint accepts the same shape: full-text `q`, `type`, `status`, requested `facets`, pagination, relation filters, and arbitrary `meta_` query parameters [@search-api]. It passes metadata filters without the `meta_` prefix and relation filters as Elasticsearch field names, so the portal does not need to know the Elasticsearch document layout beyond public query parameter names [@search-api].

## Configured Facets

The portal does not hard-code institution-specific metadata facets. On mount, `SearchPage` loads `/v1/portal/config` and reads `facet_fields` grouped by record type [@search-page]. The portal config API rebuilds `facet_fields` from active `FieldDefinition` rows where `is_facet` is true, then returns that derived config to callers [@portal-api].

The settings screen still contains an older faceting editor that stores `facet_fields` by record type and saves changes to `/v1/portal/config`, but the backend's public config response derives the effective facet list from field definitions on read [@settings-screen] [@portal-api]. That makes schema `is_facet` flags authoritative for portal search; see [Schema Configured Portal Facets](../../decisions/frontend/schema-configured-portal-facets).

## Facet Rendering

Search results return `facets` as named buckets with `value` and `count`, matching the `SearchResponse` and `FacetBucket` interfaces in the portal API client [@portal-client]. `SearchPage` always renders type and status facets when buckets exist, then renders configured metadata facet panels from `meta_<field>` aggregation names [@search-page].

Relation facets appear only when all types are searched or the active type is `object`. The page maps `related_entities`, `related_places`, and `related_occurrences` buckets to `rel_entity`, `rel_place`, and `rel_occurrence` URL parameters [@search-page]. The backend then converts those parameters back to relation keyword filters for Elasticsearch [@search-api].

## Results And Detail Navigation

Each result row links by record type: Entities go to `/entities/<id>`, Places to `/places/<id>`, Occurrences to `/occurrences/<id>`, and Objects to `/objects/<id>` [@search-page]. Before following the link, the portal saves the current search URL so detail pages can offer a return path to the same result state [@search-page].

Object results get thumbnail URLs opportunistically. After search returns, the page loads media for object hits, chooses the primary ready file or first ready file, and builds a raw media URL through the portal API base [@search-page] [@portal-client]. That keeps search result cards lightweight: the search API returns record summaries and facets, while the object media endpoint supplies thumbnails only where needed.
