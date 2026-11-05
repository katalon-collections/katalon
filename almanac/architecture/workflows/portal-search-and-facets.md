---
title: "Portal Search And Facets"
summary: "Portal search turns URL state into `/v1/search` queries with text, record type, metadata facets, relation facets, pagination, and detail navigation."
topics: [architecture, workflows, search, portal, facets, frontend]
sources:
  - id: facet-service
    type: file
    path: backend/src/katalon/services/facet_service.py
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
  - id: detail-layout
    type: file
    path: frontend/portal/src/components/DetailPageLayout.tsx
  - id: back-to-search-hook
    type: file
    path: frontend/portal/src/hooks/useBackToSearch.ts
  - id: search-result-navigation
    type: file
    path: frontend/portal/src/components/SearchResultNavigation.tsx
---

Portal search is the public-facing consumer of Katalon's Elasticsearch workflow. The React page stores query text, type filters, metadata facets, relation facets, and page number in the URL, asks `/v1/search` for matching records, and renders links to the record detail routes [@search-page]. The backend search endpoint normalizes those parameters into one search-service call and defaults anonymous requests to public records when no status is supplied [@search-api]. The indexed data and aggregation behavior are explained in [Search And Indexing](search-and-indexing).

## URL State And Backend Parameters

`SearchPage` reads `q`, `type`, `status`, `page`, `sort`, repeated `meta_*`, `range_<field>_from`, `range_<field>_to`, `rel_entity`, `rel_place`, `rel_occurrence`, and `rel_collection` parameters from `useSearchParams()` [@search-page]. It turns those values into a request to `/v1/search`, including `page_size=20` and a comma-separated `facets` list when configured metadata facet fields are available [@search-page]. Repeated values of one facet — metadata, status, or a relation facet — are combined as OR; filters across different facets remain conjunctive. Number limits are inclusive, may be open on either side, and reject non-finite values or an inverted range [@search-page] [@search-api].

The sort dropdown offers Relevance (empty value, omitted from the request), `idno_asc`, `title_asc`, `newest`, and `oldest` [@search-page]. Relevance on a non-empty query orders by Elasticsearch `_score`; on an empty query the backend substitutes `idno_asc` for a deterministic order, since `match_all` gives every hit the same score (see [Search And Indexing](search-and-indexing)) [@search-api].

Submitting the result page's refine field replaces or clears `q`, resets pagination to page one, and retains the active type, metadata, and relation filters [@search-page].

`/advanced-search` builds a versioned query from schema fields instead of free text. A query selects one result type, combines rule groups with all/any, and can nest conditions through at most two relation fields. Strict vocabulary fields load their terms through the field-scoped public schema route and require a selection; free vocabulary fields use the same terms as suggestions while retaining free input. The query is base64url-encoded in `aq` and sent as JSON to `POST /portal/v1/search/advanced`; the shared `/search` page then provides the same result cards, refinements, facets, pagination, and stable URL state as quick search [@advanced-page] [@search-page] [@portal-api].

The backend endpoint accepts the same shape: full-text `q`, `type`, `status`, requested `facets`, pagination, relation filters, and arbitrary `meta_` query parameters [@search-api]. It passes metadata filters without the `meta_` prefix and relation filters as Elasticsearch field names, so the portal does not need to know the Elasticsearch document layout beyond public query parameter names [@search-api]. Because index documents carry `facet_all_<field>` for every public field, the public portal endpoints additionally whitelist every requested facet name against the active `is_facet` field definitions (plus portal-configured `inherited_*` and relation facets) and silently drop unknown names — without this gate anonymous callers could aggregate any public field [@portal-api].

## Configured Facets

The portal does not hard-code institution-specific metadata facets. On mount, `SearchPage` loads `/v1/portal/config` and reads `facet_fields` (ordered facet names per record type) and `facet_kinds` (kind and display hints per name) [@search-page]. Both come from `services/facet_service.portal_facets()`, the single facet catalog that portal config, portal search and the index builder share [@facet-service]. Facet names: `<field>` for public `is_facet` fields, `<group>__<child>` for group sub-fields, `inherited_*` and `related_*` from the saved portal choice, and `relfacet_<key>` for configured relation facets. Kinds: `terms`, `numeric`, `boolean`, `date` (date field with `settings.facet_granularity`), `tree` (vocab field on a hierarchical vocabulary), `inherited`, `related`, `relation`. `PortalConfig.facet_order` orders them per type; names missing there keep their default position (schema order, then inherited/related, then relation facets) [@facet-service] [@portal-api]. Search requests may only aggregate catalog facets; unknown names are dropped.

The settings screen stores `facet_fields` by record type and saves changes to `/v1/portal/config`. Its reserved `_system` entry controls the global type and status facets; missing `_system` keeps both visible for compatibility with existing configurations. In addition to ordinary schema fields, the screen derives selectable inherited facets from relation fields whose settings contain both `target_type` and `inherited_fields`, then names them as `inherited_<target_type>_<field>` [@settings-screen]. The backend's public config response still derives ordinary schema facets from active field definitions on read [@portal-api]. That makes schema `is_facet` flags authoritative for direct metadata facets, while selected inherited facet keys opt into the Elasticsearch projection described in [Inherited Fields In Elasticsearch](../../decisions/search/inherited-fields-in-elasticsearch).

## Facet Rendering

Active type, status, subtype, relation, metadata, and numeric-range filters appear as removable pills below the result count, including on mobile. Each pill removes only its own selected value (both bounds for a numeric range), resets the page to one, and preserves the query, sort, and remaining filters. Labels reuse the sidebar's schema labels, relation titles, tree paths, date buckets, and translated boolean values; advanced-query rules remain in their existing summary [@search-page].

Search results return categorical `facets` as named buckets with `value` and `count`, plus `numeric_facets` with `min` and `max` bounds, matching the portal client response types [@portal-client]. `SearchPage` renders type and status only when enabled in `_system`. The type facet stays single-select (exclusive), since it determines which configured facet set is shown; picking a type replaces rather than adds to the selection. Every other facet — status, relation facets, and configured metadata facets — is multi-select (additive, OR within the facet): clicking a value toggles it in the URL parameter list rather than replacing it. A facet's reset action appears below its values only while that facet is active. Configured number fields render precise native From/To inputs and one shared two-handle range track; unfiltered inputs display the aggregation's min/max without adding a URL filter, and remain available for exact values and accessibility [@search-page]. Other configured metadata panels come from `meta_<field>` aggregation names. Their headings use the public schema field label for the active type, or the linked-facet label pattern for inherited relation facets [@search-page].

`SearchPage` renders every facet in one loop in `facet_fields` order and dispatches on its kind [@search-page]. Facet value sort order and the initially visible value count are configured in `PortalConfig` (`facet_sort`: global default `count` or `alpha`; `facet_sort_overrides`: per-type, per-facet override `count` or `alpha` for categorical facets of kind `terms`, `inherited`, `related`, and `relation`, edited directly in `FacetOrderList`; `facet_initial_count`, default 10), and threaded through `facet_service.portal_facets()` and `portal_public.py` into `search_service.search()` and `elasticsearch.search_documents()` [@settings-screen] [@portal-api] [@facet-service] [@search-service]. The Elasticsearch `terms` aggregation for each `meta_<field>` fetches up to 100 buckets (500 for alphabetical relation facets, sorted by display title in `search_service`) with the configured `order`, decoupled from `facet_initial_count` so "show more" can reveal further values already present in the response without a second round-trip [@search-service]. `FacetPanel` renders only the configured initial slice plus any already-active values from beyond that slice (so a selected value never silently disappears), and exposes "show more"/"show less" once more values exist than are shown [@search-page].

The generic `related_*` facets (all relations to a target type) map their buckets to repeated `rel_entity`, `rel_place`, `rel_occurrence`, and `rel_collection` URL parameters [@search-page]; the backend converts them back to keyword filters [@search-api] [@portal-api]. Their titles only include linked records with a public status that are not soft-deleted.

All other facets use `meta_<name>=<value>`; the API maps the name to the right index field via the catalog [@portal-api] [@search-service]:

- **Relation facets** (`PortalConfig.relation_facets`: key, label, target type, relation types, optional target subtypes, direction) are indexed as `facet_rel_<key>` (`"<id>|<title>"`, aggregated) and `facet_relid_<key>` (filtered by id, so two people with the same name stay apart); the portal shows the title. Changing a relation facet requests a rebuild of the affected types.
- **Date facets** store buckets in `facet_date_<name>` from every value (all group instances): single dates and `~` give their year's bucket, open intervals (`YYYY/`, `/YYYY`) the bucket of the given year, closed intervals every covered bucket — or only start and end bucket when longer than five decades — and implausible years (< 1000 or in the future) are ignored [@facet-service]. They aggregate chronologically with up to 500 buckets; the portal labels them "1910er"/"1910s" or "19. Jh."/"19th c.". Changing the granularity rebuilds the type.
- **Tree facets** index every value's ancestor chain in `facet_path_<name>`, so filtering on a node includes all narrower terms. The search API counts exactly the children of the top level and of every `expand_<name>=<id>` node (one `terms` aggregation with an `include` list, no 100-bucket limit) and returns them as `tree_facets` with labels, `has_children`, and the ancestor path of every active value for the breadcrumb. `TreeFacetPanel` expands nodes on demand (fetching only the counts, not the result list) and offers a filter field above 50 children. Moving a term to another parent rebuilds every type with a field on that vocabulary; renaming a term needs no rebuild for tree facets (labels are resolved per request).

### Status Filtering And Self-Excluding Aggregations

Status is not a single uniform filter: anonymous portal visitors are hard-locked to `PUBLIC_STATUSES` (`public`, `published`) for security, while authenticated staff previewing the portal may additionally choose to filter by one or more statuses as an ordinary facet. `search_documents()` keeps these as two separate Elasticsearch filter channels — a hard `status` term that is always applied and never excluded from any facet's own aggregation, and a togglable `status_facet` list that behaves like every other additive facet [@search-service]. `portal_public.py` only ever populates the hard channel for anonymous requests and only ever populates `status_facet` for staff, so an anonymous visitor's `by_status` aggregation can never reveal draft or internal record counts regardless of what status values they pass on the URL [@portal-api].

All additive facets (status, the four relation facets, and every configured metadata facet) use the same "global + filtered, minus this facet's own active filter" Elasticsearch aggregation shape, so selecting one value never removes its sibling values from the facet panel — the panel keeps offering every value a user could still add, with counts computed as if that one facet were not yet filtered [@search-service].

For an advanced query, the selected result type replaces the ordinary type filter and the type facet is hidden. Metadata, numeric range, and relation facets remain usable and are included in the advanced POST body [@search-page] [@portal-api].

## Configured Result Subtitles

Portal settings store an ordered `subtitle_fields` list per record type. Admins can choose the type/status pseudo-fields and schema fields that are already enabled as facets. The public search route passes this configuration into the search service, which returns display-ready `subtitle_values`; without a configured list, the portal leaves the subtitle line empty [@settings-screen] [@portal-api] [@search-api] [@search-service] [@search-page].

## Results And Detail Navigation

In paged mode, multi-page results offer a page-number input beside the numbered buttons, submitted with Enter or Go. Both paths preserve filters and sort, and reject unreachable pages before changing the URL or replacing results. The reachability check mirrors Elasticsearch's 10,000-hit forward window and, for fixed sorts or an empty query, its reversed tail window. An unavailable target shows a localized hint to narrow the search. Infinite mode and single-page results omit the input [@search-page].

Each result row and grid card links by record type: Entities go to `/entities/<id>`, Places to `/places/<id>`, Occurrences to `/occurrences/<id>`, and Objects to `/objects/<id>` [@search-page]. Every result also carries a small type/subtype badge beside the title, independent of the admin-configured `subtitle_fields`, so the record type or specific subtype stays visible even when a portal's subtitle configuration is empty [@search-page]. Before following the link, the portal saves the current search URL so detail pages can offer a return path to the same result state [@search-page].

The portal also stores the loaded result IDs, page and position for the clicked row in session storage [@search-page] [@back-to-search-hook]. Public record detail pages use that context for small previous/next controls beside the heading [@search-result-navigation]. They stay within the original URL filters and explicit sort; ordinary paged searches load the adjacent result page on demand. Advanced-search navigation intentionally stays within already loaded results, because its query is POST-only rather than replayable from the URL [@back-to-search-hook].

Object results get thumbnail URLs opportunistically. After search returns, the page loads media for object hits, chooses the primary ready file or first ready file, and builds the public JPEG-thumbnail endpoint through `mediaThumbnailUrl` [@search-page] [@portal-client]. Object rows retain their thumbnail area when no ready media exists; entity, place, and occurrence rows render no media column. That keeps search result cards lightweight: the search API returns record summaries and facets, while the object media endpoint supplies thumbnails only where needed.

## Facet Click-Through From Detail Pages

Detail pages expose the same `is_facet` metadata as clickable filter links, not just search-page facet panels. `GET /portal/v1/schema/{target_type}` now also returns each field's `is_facet` flag [@portal-api]. `DetailPageLayout`'s `MainField` and `SidebarField` check it before falling back to the ordinary label/authority-link rendering: when set, every repeatable value renders as its own pill link instead of plain text [@detail-layout]. `CollectionDetailPage`, which renders its schema fields manually rather than through `DetailPageLayout`, applies the same branch inline [@detail-layout].

The link target reuses the exact query-parameter contract `SearchPage` already reads: `/search?type=<recordType>&meta_<field>=<value>` for ordinary fields, or `range_<field>_from`/`range_<field>_to` set to the same value for number fields, scoping results to the clicked record's own type [@detail-layout] [@search-page]. Each pill's raw filter value mirrors the backend's `_extract_facet_value` extraction (dict values use `label` then `value`; booleans stringify as Python's `"True"`/`"False"`) so the link matches the indexed `facet_all_<field>` term exactly, while the pill's visible text still goes through the normal locale-aware `renderFieldValue` formatting (e.g. formatted dates) [@detail-layout] [@search-service].

Pills of tree facets link with the term id (`facetItems` returns it for vocabulary entries), pills of date facets with the value's bucket [@detail-layout]. Relation fields keep their existing `RelationFieldRow` rendering regardless of `is_facet`. In the relations list, a relation covered by a relation facet of the current record type gets a small "weitere" link to `/search?type=<type>&meta_relfacet_<key>=<linked id>`; on entity, place and occurrence pages, `RelatedObjects` links "<objects> mit <role>" for every object relation facet that targets the current record. Facets restricted to target subtypes get no link, because the linked record's subtype is not known client-side.
