---
title: "Schema Configured Portal Facets"
summary: "Portal metadata facets come from schema field definitions instead of hard-coded portal fields."
topics: [decisions, frontend, portal, search, facets, schema]
sources:
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
  - id: settings-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: portal-search
    type: file
    path: frontend/portal/src/pages/SearchPage.tsx
  - id: search-api
    type: file
    path: backend/src/katalon/api/v1/search.py
  - id: schema-api
    type: file
    path: backend/src/katalon/api/v1/schema_admin.py
  - id: portal-api
    type: file
    path: backend/src/katalon/api/v1/portal.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
---

Portal metadata facets are configured through Katalon's schema layer instead of being hard-coded in the portal frontend. Field definitions carry an `is_facet` flag, the public portal config endpoint derives `facet_fields` from non-deleted field definitions with that flag, and the portal search page asks `/v1/search` for aggregations over those configured metadata fields [@models] [@portal-api] [@portal-search] [@search-api]. This ties faceting to the same metadata model described in [Schema Engine](../../concepts/metadata/schema-engine) and keeps institution-specific filters out of portal page code.

## Context

Katalon's record metadata is dynamic. `FieldDefinition` rows define each field's target type, name, labels, field type, searchability, list/detail visibility, facet flag, deletion state, and settings JSON [@models]. Because different installations can define different fields, a fixed facet list in `SearchPage` would make the portal depend on one institution's schema.

The admin UI exposes the facet flag where fields are edited. `ScreenSchema` includes `is_facet` in its field form state, renders an `Als Facette verwenden` checkbox for non-vocabulary-term fields, and sends `is_facet` when saving field definitions [@schema-screen]. The settings screen also has a faceting section that loads schema fields by record type and saves a `facet_fields` object to `/v1/portal/config` [@settings-screen].

## Decision

The effective public metadata facet list is derived from schema field definitions. `GET /v1/portal/config` loads the singleton portal config, queries `FieldDefinition.target_type` and `FieldDefinition.name` where `is_facet` is true and `is_deleted` is false, groups the names by target type, adds the saved `_system` selection for the built-in type and status facets, and returns it [@portal-api]. Existing configurations without `_system` keep both built-in facets visible.

The portal search page consumes that public config. On mount, it calls `api.portal.config()`, stores `facet_fields`, and builds the `/v1/search` `facets` query parameter from the active record type's configured fields or from all configured fields when no type filter is active [@portal-search]. It renders each configured metadata facet from response keys named `meta_<field>`, labels it from the public schema in the active language with German/English fallback, and writes every selected value back into the URL as a repeated `meta_<field>=<value>` parameter [@portal-search].

The backend search endpoint accepts the portal's shape. It parses the comma-separated `facets` parameter into a list of metadata fields, collects all values of every repeated `meta_` query parameter, removes that prefix for `extra_filters`, and passes both values into `search_service.search()` [@search-api]. Values of one field are OR-connected. Each metadata aggregation excludes only its own selected values, leaving further values visible while retaining the other active filters. Anonymous callers are restricted to public records when no explicit status filter is supplied [@search-api].

## Consequences

Schema changes and search indexing are coupled. `schema_admin.update_field()` detects changes to `is_facet` and enqueues a type-specific reindex when the flag changes, so the search index can expose the new aggregation contract [@schema-api]. The public portal will not show a metadata facet just because `SearchPage` has code for it; the field must be an active schema field marked as a facet [@portal-api] [@portal-search].

The current code has two admin paths with different authority. The settings faceting section can save `portal_config.facet_fields`, and `PortalConfig` still has a `facet_fields` JSON column [@settings-screen] [@models]. However, `GET /v1/portal/config` overwrites the returned `facet_fields` from `FieldDefinition.is_facet`, so the schema field flag is the effective public source for portal search [@portal-api]. Future work should either align the settings UI with the schema flag or remove the older saved-list path.

For the full query flow from URL state to result rendering, see [Portal Search And Facets](../../architecture/workflows/portal-search-and-facets).
