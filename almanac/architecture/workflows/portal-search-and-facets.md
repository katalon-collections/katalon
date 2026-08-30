---
title: "Portal Search And Facets"
summary: "Portal search turns URL state into `/v1/search` queries with text, record type, metadata facets, relation facets, pagination, and detail navigation."
topics: [architecture, workflows, search, portal, facets, frontend]
sources:
  - id: search-api
    type: file
    path: backend/src/katalon/api/v1/search.py
  - id: search-service
    type: file
    path: backend/src/katalon/services/search_service.py
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
    path: backend/src/katalon/api/v1/portal_public.py
  - id: advanced-page
    type: file
    path: frontend/portal/src/pages/AdvancedSearchPage.tsx
---

Portal search is the public-facing consumer of Katalon's Elasticsearch workflow. The React page stores query text, type filters, metadata facets, relation facets, and page number in the URL, asks `/v1/search` for matching records, and renders links to the record detail routes [@search-page]. The backend search endpoint normalizes those parameters into one search-service call and defaults anonymous requests to public records when no status is supplied [@search-api]. The indexed data and aggregation behavior are explained in [Search And Indexing](search-and-indexing).

## URL State And Backend Parameters

`SearchPage` reads `q`, `type`, `status`, `page`, repeated `meta_*`, `rel_entity`, `rel_place`, and `rel_occurrence` parameters from `useSearchParams()` [@search-page]. It turns those values into a request to `/v1/search`, including `page_size=20` and a comma-separated `facets` list when configured metadata facet fields are available [@search-page]. Repeated values of one metadata field are combined as OR; filters from different metadata fields remain conjunctive [@search-page] [@search-api].

Submitting the result page's refine field replaces or clears `q`, resets pagination to page one, and retains the active type, metadata, and relation filters [@search-page].

`/advanced-search` builds a versioned query from schema fields instead of free text. A query selects one result type, combines rule groups with all/any, and can nest conditions through at most two relation fields. Strict vocabulary fields load their terms through the field-scoped public schema route and require a selection; free vocabulary fields use the same terms as suggestions while retaining free input. The query is base64url-encoded in `aq` and sent as JSON to `POST /portal/v1/search/advanced`; the shared `/search` page then provides the same result cards, refinements, facets, pagination, and stable URL state as quick search [@advanced-page] [@search-page] [@portal-api].

The backend endpoint accepts the same shape: full-text `q`, `type`, `status`, requested `facets`, pagination, relation filters, and arbitrary `meta_` query parameters [@search-api]. It passes metadata filters without the `meta_` prefix and relation filters as Elasticsearch field names, so the portal does not need to know the Elasticsearch document layout beyond public query parameter names [@search-api].

## Configured Facets

The portal does not hard-code institution-specific metadata facets. On mount, `SearchPage` loads `/v1/portal/config` and reads `facet_fields` grouped by record type [@search-page]. The portal config API rebuilds `facet_fields` from active `FieldDefinition` rows where `is_facet` is true, then returns that derived config to callers [@portal-api].

The settings screen stores `facet_fields` by record type and saves changes to `/v1/portal/config`. Its reserved `_system` entry controls the global type and status facets; missing `_system` keeps both visible for compatibility with existing configurations. In addition to ordinary schema fields, the screen derives selectable inherited facets from relation fields whose settings contain both `target_type` and `inherited_fields`, then names them as `inherited_<target_type>_<field>` [@settings-screen]. The backend's public config response still derives ordinary schema facets from active field definitions on read [@portal-api]. That makes schema `is_facet` flags authoritative for direct metadata facets, while selected inherited facet keys opt into the Elasticsearch projection described in [Inherited Fields In Elasticsearch](../../decisions/search/inherited-fields-in-elasticsearch).

## Facet Rendering

Search results return `facets` as named buckets with `value` and `count`, matching the `SearchResponse` and `FacetBucket` interfaces in the portal API client [@portal-client]. `SearchPage` renders type and status only when enabled in `_system`; active URL filters do not override that configuration. A facet's reset action appears below its values only while that facet is active. Configured metadata panels come from `meta_<field>` aggregation names. Their headings use the public schema label for the active portal language, falling back through German, English, and finally the internal field name [@search-page]. Their Elasticsearch aggregation excludes that field's own active values while retaining all other filters, so further values remain selectable with meaningful counts [@search-service]. Inherited fields use the same repeated `meta_` URL and backend filter path as direct metadata facets; the field key itself carries the `inherited_<target_type>_<field>` prefix, so the portal can label it as a linked-record facet without adding another query parameter family [@search-page].

Relation facets appear only when all types are searched or the active type is `object`. The page maps `related_entities`, `related_places`, and `related_occurrences` buckets to `rel_entity`, `rel_place`, and `rel_occurrence` URL parameters [@search-page]. The backend then converts those parameters back to relation keyword filters for Elasticsearch [@search-api].

For an advanced query, the selected result type replaces the ordinary type filter and the type facet is hidden. Metadata and relation facets remain usable and are included in the advanced POST body [@search-page] [@portal-api].

## Configured Result Subtitles

Portal settings store an ordered `subtitle_fields` list per record type. Admins can choose the type/status pseudo-fields and schema fields that are already enabled as facets. The public search route passes this configuration into the search service, which returns display-ready `subtitle_values`; without a configured list, the portal retains the type-and-status fallback [@settings-screen] [@portal-api] [@search-api] [@search-service] [@search-page].

## Results And Detail Navigation

Each result row links by record type: Entities go to `/entities/<id>`, Places to `/places/<id>`, Occurrences to `/occurrences/<id>`, and Objects to `/objects/<id>` [@search-page]. Before following the link, the portal saves the current search URL so detail pages can offer a return path to the same result state [@search-page].

Object results get thumbnail URLs opportunistically. After search returns, the page loads media for object hits, chooses the primary ready file or first ready file, and builds the public JPEG-thumbnail endpoint through `mediaThumbnailUrl` [@search-page] [@portal-client]. That keeps search result cards lightweight: the search API returns record summaries and facets, while the object media endpoint supplies thumbnails only where needed.
