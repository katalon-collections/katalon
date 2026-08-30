---
title: "Portal Routes"
summary: "Reference for public portal browser routes, page components, and backend API resources."
topics: [reference, frontend, routing, portal]
sources:
  - id: portal-app
    type: file
    path: frontend/portal/src/App.tsx
  - id: portal-client
    type: file
    path: frontend/portal/src/api/client.ts
---

Portal routes are browser routes rendered through React Router. `App` wraps `AppInner` in `HelmetProvider` and `BrowserRouter`, and `AppInner` mounts a fixed set of public routes below the shared banner, header, footer, and feedback button [@portal-app]. The portal API client uses `VITE_API_URL` as an optional host prefix and sends its public reads to the anonymous `/portal/v1` API surface [@portal-client].

## Browser Routes

| Path | Component | Main API resources |
|---|---|---|
| `/` | `HomePage` | Portal config and page-specific resources |
| `/search` | `SearchPage` | `/portal/v1/search` |
| `/advanced-search` | `AdvancedSearchPage` | `/portal/v1/schema/:type`, field-scoped vocabulary terms; results use `/portal/v1/search/advanced` |
| `/objects/:id` | `ObjectDetailPage` inside `ErrorBoundary` | `/portal/v1/objects/:id`, `/portal/v1/objects/:id/media`, `/portal/v1/relations` |
| `/entities/:id` | `EntityDetailPage` | `/portal/v1/entities/:id`, `/portal/v1/relations` |
| `/places/:id` | `PlaceDetailPage` | `/portal/v1/places/:id`, `/portal/v1/relations` |
| `/occurrences/:id` | `OccurrenceDetailPage` | `/portal/v1/occurrences/:id`, `/portal/v1/relations` |
| `/page/:slug` | `StaticPageView` | `/portal/v1/pages/:slug` |

The route table is declared directly in `AppInner`; there is no generated route registry or nested route file for the portal [@portal-app]. Portal layout, theming, and React Router ownership are covered by [Portal Routing And Theming](../../architecture/frontend/portal-routing-and-theming).

## Header Navigation

The header logo links to `/`. The fixed collection links point to `/search?q=&type=object`, `/search?q=&type=entity`, `/search?q=&type=place`, and `/search?q=&type=occurrence` [@portal-app].

The header search is global. On submit it navigates to `/search?q=<term>` without inheriting a type from the current page. The adjacent advanced-search link opens `/advanced-search`, where users choose a result type explicitly [@portal-app].

## Autocomplete Paths

Header autocomplete calls `/portal/v1/search` with `q` and `page_size=5` across all four public record types. Suggestions link to detail paths based on `record_type`: `entity` maps to `/entities/:id`, `place` to `/places/:id`, `occurrence` to `/occurrences/:id`, and every other type falls back to `/objects/:id` [@portal-app].

## API Client Endpoints

| Client member | Endpoint shape |
|---|---|
| `objects.list` | `/portal/v1/objects?...` |
| `objects.get` | `/portal/v1/objects/:id` |
| `objects.media` | `/portal/v1/objects/:id/media` |
| `entities.get` | `/portal/v1/entities/:id` |
| `places.get` | `/portal/v1/places/:id` |
| `occurrences.get` | `/portal/v1/occurrences/:id` |
| `relations.forRecord` | `/portal/v1/relations?from_type=...` and `/portal/v1/relations?to_type=...` |
| `portal.config` | `/portal/v1/portal/config` |
| `portal.schema` | `/portal/v1/schema/:type` |
| `pages.list` | `/portal/v1/pages` |
| `pages.get` | `/portal/v1/pages/:slug` |
| `vocabularies.list` | `/portal/v1/vocabularies` |
| `vocabularies.terms` | `/portal/v1/vocabularies/:id/terms` |
| `search.query` | `/portal/v1/search?...` |
| `search.advanced` | `POST /portal/v1/search/advanced` |
| `banners.activePortal` | `/portal/v1/banners/active/portal` |

`relations.forRecord` performs two API reads, one where the current record is `from_*` and one where it is `to_*`, then concatenates the relation lists [@portal-client]. Search behavior and facet query parameters are described in [Portal Search And Facets](../../architecture/workflows/portal-search-and-facets).

## Footer Routes

The footer loads static page summaries from `api.pages.list()` and creates one `/page/<slug>` link for each returned page. It also links the API documentation at `/api/docs` [@portal-app].
