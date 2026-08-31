---
title: "Portal Routing And Theming"
summary: "The public portal is a browser-routed React app that reads public API endpoints, runtime theme tokens, portal configuration, static pages, banners, and feedback affordances."
topics: [architecture, frontend, portal, routing, theming]
sources:
  - id: portal-app
    type: file
    path: frontend/portal/src/App.tsx
  - id: portal-styles
    type: file
    path: frontend/portal/src/styles.css
  - id: portal-client
    type: file
    path: frontend/portal/src/api/client.ts
  - id: detail-layout
    type: file
    path: frontend/portal/src/components/DetailPageLayout.tsx
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
  - id: portal-public-api
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
---

The public portal is a React Router application for collection discovery, record detail pages, static content, and site-level presentation settings. Its entry component defines browser routes for home, search, object detail, entity detail, place detail, occurrence detail, static pages, and staff login; it also mounts the header, footer, banner bar, and runtime theme loading in one app frame [@portal-app]. The portal API client uses the dedicated `/portal/v1` read model and exposes typed readers for records, media, relations, portal config, pages, vocabularies, search, and active portal banners [@portal-client] [@portal-public-api].

## Browser Routes

`App` wraps the portal in `HelmetProvider` and `BrowserRouter`, then `AppInner` renders routes for `/`, `/search`, `/advanced-search`, `/login`, `/objects/:id`, `/entities/:id`, `/places/:id`, `/occurrences/:id`, and `/page/:slug` [@portal-app]. Unlike the admin shell, portal routes are path-based because public URLs need stable, shareable record and page addresses [@portal-app].

The header provides admin-configurable type-scoped navigation links and a debounced autocomplete search. `browse_enabled_types` controls which of the four inventory types appear in the header; it hides an empty browsing entry without restricting public detail URLs. It preserves the current `type` query parameter when the user searches from a scoped page and maps search hits to the corresponding detail URL based on `record_type` [@portal-app]. On mobile, the search input's relative-positioned wrapper, not only the form, expands to the full header width so the autocomplete dropdown keeps the same alignment boundary [@portal-app] [@portal-styles]. The footer fetches published static page summaries and links each published slug under `/page/<slug>` [@portal-app] [@pages-api].

## Public API Surface

The portal client sends an existing in-memory Katalon access token when one is present, refreshes it once after a `401`, and otherwise keeps anonymous-read semantics [@portal-client]. `/login` uses the existing `/v1/auth/token` endpoint; its host-only refresh cookie is also recognized by the Admin UI on the same origin when that application starts. A recognised staff role (`superuser`, `admin`, `editor`, `cataloger`, or `viewer`) receives internal records where its backend read permission allows them, plus all schema fields and internal search; a future public-account role remains on the anonymous projection [@portal-client] [@portal-public-api].

The backend confines this anonymous surface to the four inventory record families. It has no Procedure endpoint, and it returns relations only where both endpoints are visible inventory records. Its response models are public projections: they omit record versions and search vectors; relation responses omit relation metadata; and public responses return their own `/portal/v1` `_links` instead of the authenticated `/v1` links [@portal-public-api].

Backend portal config is stored as the singleton `portal_config` row with defaults for title, subtitle, hero text, featured object ids, facet fields, result-subtitle fields, enabled browsing types, accent color, logo URL, placeholder image URL, extra CSS color tokens, and detail-sidebar position [@portal-api]. The read endpoint applies those defaults before Pydantic response validation, so rows created before newer config columns existed still return a complete public config [@portal-api]. `GET /v1/portal/config` builds `facet_fields` dynamically from non-deleted `field_definitions` with `is_facet`, while `PUT /v1/portal/config` and logo upload require an admin role [@portal-api]. This makes search facets an effect of schema configuration rather than a separate portal-only list [@portal-api].

Static pages have a public list and public by-slug read path that only return `is_published` pages, plus admin-only CRUD paths that can see unpublished pages [@pages-api]. Banners have public active endpoints for admin and portal surfaces, filtered by active flag, expiration, and surface visibility; banner CRUD remains admin-only [@banners-api].

## Record Detail Layout

The four public record-detail pages share `DetailPageLayout`. Public field definitions select the main column or metadata sidebar through `detail_slot`; one field per type or subtype can take the description role through `detail_role`. The portal setting `detail_sidebar_position` places the narrow sidebar left or right, while pages without main-column content collapse to one bounded metadata column [@detail-layout] [@portal-api] [@portal-client].

## Runtime Theme Layers

The portal loads `/portal/v1/theme` at startup and passes the manifest to `applyTheme`; failure falls back to default tokens [@theme-loader] [@theme-inject] [@portal-client]. `applyTheme` merges default CSS tokens with manifest tokens, injects an optional body-font stylesheet, and updates the favicon under `/themes/<file>` [@theme-inject]. The configured portal `site_title` owns the visible portal brand and the Helmet title template, so a theme name cannot replace the institution's browser title [@portal-app] [@theme-inject].

After the base theme loads, `AppInner` reads portal config and applies `color_tokens` and `accent_color` directly to `document.documentElement` [@portal-app]. The resulting order is default theme tokens, theme manifest tokens, then portal-config overrides; that gives operators a persistent configuration layer without rebuilding the frontend [@portal-app] [@theme-inject].

The routing frame connects to content workflows rather than owning them. Search pages and facet behavior depend on search endpoints, while record detail pages use media and IIIF data exposed by object endpoints. Those backend workflows are separate from this portal frame, but their public outputs are consumed through the portal client [@portal-client].
