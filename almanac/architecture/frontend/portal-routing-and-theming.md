---
title: "Portal Routing And Theming"
summary: "The public portal is a browser-routed React app that reads public API endpoints, runtime theme tokens, portal configuration, static pages, banners, and feedback affordances."
topics: [architecture, frontend, portal, routing, theming]
sources:
  - id: portal-app
    type: file
    path: frontend/portal/src/App.tsx
  - id: portal-client
    type: file
    path: frontend/portal/src/api/client.ts
  - id: theme-loader
    type: file
    path: frontend/portal/src/theme/loader.ts
  - id: theme-inject
    type: file
    path: frontend/portal/src/theme/inject.ts
  - id: portal-api
    type: file
    path: backend/src/katalon/api/v1/portal.py
  - id: pages-api
    type: file
    path: backend/src/katalon/api/v1/pages.py
  - id: banners-api
    type: file
    path: backend/src/katalon/api/v1/banners.py
---

The public portal is a React Router application for collection discovery, record detail pages, static content, and site-level presentation settings. Its entry component defines browser routes for home, search, object detail, entity detail, place detail, occurrence detail, and static pages; it also mounts the header, footer, banner bar, feedback button, and runtime theme loading in one app frame [@portal-app]. The portal API client is intentionally lighter than the admin client: it performs public `GET` requests against `/v1` endpoints and exposes typed readers for records, media, relations, portal config, pages, vocabularies, search, and active portal banners [@portal-client].

## Browser Routes

`App` wraps the portal in `HelmetProvider` and `BrowserRouter`, then `AppInner` renders routes for `/`, `/search`, `/objects/:id`, `/entities/:id`, `/places/:id`, `/occurrences/:id`, and `/page/:slug` [@portal-app]. Unlike the admin shell, portal routes are path-based because public URLs need stable, shareable record and page addresses [@portal-app].

The header provides type-scoped navigation links and a debounced autocomplete search. It preserves the current `type` query parameter when the user searches from a scoped page and maps search hits to the corresponding detail URL based on `record_type` [@portal-app]. The footer fetches published static page summaries and links each published slug under `/page/<slug>` [@portal-app] [@pages-api].

## Public API Surface

The portal client has one shared `get<T>` helper and no token lifecycle, so every exported call assumes public-read semantics [@portal-client]. Its record functions read object lists and detail records, object media, individual entity/place/occurrence records, two-way relation lists, portal config, static pages, vocabularies, Elasticsearch-backed search, and active portal banners [@portal-client].

Backend portal config is stored as the singleton `portal_config` row with defaults for title, subtitle, hero text, featured object ids, facet fields, accent color, logo URL, placeholder image URL, and extra CSS color tokens [@portal-api]. `GET /v1/portal/config` builds `facet_fields` dynamically from non-deleted `field_definitions` with `is_facet`, while `PUT /v1/portal/config` and logo upload require an admin role [@portal-api]. This makes search facets an effect of schema configuration rather than a separate portal-only list [@portal-api].

Static pages have a public list and public by-slug read path that only return `is_published` pages, plus admin-only CRUD paths that can see unpublished pages [@pages-api]. Banners have public active endpoints for admin and portal surfaces, filtered by active flag, expiration, and surface visibility; banner CRUD remains admin-only [@banners-api].

## Runtime Theme Layers

The portal loads `/v1/theme` at startup and passes the manifest to `applyTheme`; failure falls back to default tokens [@theme-loader] [@theme-inject]. `applyTheme` merges default CSS tokens with manifest tokens, injects an optional body-font stylesheet, updates the favicon under `/themes/<file>`, and can set `document.title` from the theme name [@theme-inject].

After the base theme loads, `AppInner` reads portal config and applies `color_tokens` and `accent_color` directly to `document.documentElement` [@portal-app]. The resulting order is default theme tokens, theme manifest tokens, then portal-config overrides; that gives operators a persistent configuration layer without rebuilding the frontend [@portal-app] [@theme-inject].

The routing frame connects to content workflows rather than owning them. Search pages and facet behavior depend on search endpoints, while record detail pages use media and IIIF data exposed by object endpoints. Those backend workflows are separate from this portal frame, but their public outputs are consumed through the portal client [@portal-client].
