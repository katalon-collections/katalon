---
title: "Schema Configured Portal Facets"
summary: "Portal facets come from one backend facet catalog built from schema field definitions and portal config instead of hard-coded portal fields."
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
  - id: facet-service
    type: file
    path: backend/src/katalon/services/facet_service.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/facetten-katalog.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/facetten-katalog.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Portal facets are configured through Katalon's schema layer and the portal config instead of being hard-coded in the portal frontend. A single backend facet catalog, `services/facet_service.portal_facets()`, decides which facets exist per record type, of which kind, in which order and with which sort; the public portal config returns that catalog and the portal search page renders it [@facet-service] [@portal-api] [@portal-search]. This ties faceting to the same metadata model described in [Schema Engine](../../concepts/metadata/schema-engine) and keeps institution-specific filters out of portal page code.

## Context

Katalon's record metadata is dynamic. `FieldDefinition` rows define each field's target type, name, labels, field type, public visibility, facet flag, deletion state, and settings JSON [@models]. Because different installations can define different fields, a fixed facet list in `SearchPage` would make the portal depend on one institution's schema.

Simple field facets were not enough for migrated collections: they also need facets over relations (for example artist or publisher), over group sub-fields, over date buckets such as decades, and over hierarchical vocabularies. Those are a core feature, not a theme workaround.

## Decision

`facet_service` is the facet catalog shared by portal config, portal search and the index builder [@facet-service]. Facet names are:

- `<field>` — a public, non-deleted field with `is_facet`; the kind follows its field type and settings,
- `<group>__<child>` — a sub-field of a group field,
- `inherited_<type>_<field>` and `related_*` — opted in through the saved portal choice `PortalConfig.facet_fields`,
- `relfacet_<key>` — a relation facet configured in `PortalConfig.relation_facets`.

Kinds are `terms`, `numeric`, `boolean`, `date` (with `settings.facet_granularity` `decade`, `century` or `year`), `tree` (vocabulary field on a hierarchical vocabulary), `inherited`, `related` and `relation` [@facet-service]. `is_facet` is independent of `show_in_detail`. `PortalConfig.facet_order` orders the facets per type; names missing there keep their default position (schema order, then inherited/related, then relation facets). Term-like facets sort by `facet_sort` (`count` or `alpha`), overridable per facet through `facet_sort_overrides` [@facet-service] [@portal-api].

`GET /v1/portal/config` returns the catalog as `facet_fields` (ordered names per type) and `facet_kinds` (kind and display hints per name), plus the reserved `_system` entry for the built-in record type, status and subtype facets; configurations without `_system` show record type and subtype [@portal-api]. The portal search page builds the `/v1/search` `facets` parameter from the active type's facets, renders them by kind, labels them from the public schema in the active language, and writes selections into the URL as repeated `meta_<field>=<value>` or inclusive `range_<field>_from`/`range_<field>_to` parameters [@portal-search].

The backend search endpoint parses `facets` and every repeated `meta_` parameter and passes them to `search_service.search()` [@search-api]. Values of one facet are OR-connected; different facets are conjunctive. Each aggregation excludes only its own filter, and relation facets always return their selected values, even outside the top buckets. Anonymous callers are restricted to public records when no explicit status filter is supplied [@search-api].

## Consequences

All derived index fields live under `facet_*` and are keyword-mapped by the existing dynamic template, so new facet kinds need no mapping change. Index documents carry `facet_all_<field>` for every public field, so toggling `is_facet` takes effect without a reindex; the public search endpoints whitelist requested facet names against the catalog and drop unknown names, otherwise anonymous callers could aggregate any public field [@schema-api] [@portal-api]. Changes to `is_public`, inherited relation settings or `relation_facets` change document content and enqueue a reindex of exactly the affected record types [@schema-api] [@portal-api].

Schema `is_facet` flags are authoritative for direct field facets: the settings screen can reorder and choose inherited, related and system facets, but it cannot show a field facet whose field is not marked as a facet [@schema-screen] [@settings-screen] [@portal-api].

For the full query flow from URL state to result rendering, see [Portal Search And Facets](../../architecture/workflows/portal-search-and-facets).
