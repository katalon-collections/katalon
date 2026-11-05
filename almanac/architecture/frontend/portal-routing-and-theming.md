---
title: "Portal Routing And Theming"
summary: "The public portal is a browser-routed React app that reads public API endpoints, runtime theme tokens, portal configuration, static pages, and banners."
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
  - id: portal-i18n
    type: file
    path: frontend/portal/src/i18n/index.ts
  - id: admin-settings
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: footer-notice-settings
    type: file
    path: frontend/admin/src/components/screens/settings/SectionFooterNotice.tsx
  - id: usage-notice
    type: file
    path: frontend/portal/src/components/UsageNotice.tsx
  - id: portal-model
    type: file
    path: backend/src/katalon/core/models.py
  - id: detail-layout
    type: file
    path: frontend/portal/src/components/DetailPageLayout.tsx
  - id: theme-loader
    type: file
    path: frontend/portal/src/theme/loader.ts
  - id: theme-inject
    type: file
    path: frontend/portal/src/theme/inject.ts
  - id: theme-api
    type: file
    path: backend/src/katalon/api/v1/theme.py
  - id: portal-vite
    type: file
    path: frontend/portal/vite.config.ts
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

The public portal is a React Router application for collection discovery, record detail pages, static content, and site-level presentation settings. Its entry component defines browser routes for home, search, collection browse/detail, object detail, entity detail, place detail, occurrence detail, static pages, and staff login; it also mounts the header, footer, banner bar, and runtime theme loading in one app frame [@portal-app]. The portal API client uses the dedicated `/portal/v1` read model and exposes typed readers for records, collections, media, relations, portal config, pages, vocabularies, search, and active portal banners [@portal-client] [@portal-public-api].

## Browser Routes

`App` wraps the portal in `HelmetProvider` and `BrowserRouter`, then `AppInner` renders routes for `/`, `/search`, `/advanced-search`, `/login`, `/collections`, `/collections/:id`, `/objects/:id`, `/entities/:id`, `/places/:id`, `/occurrences/:id`, and `/page/:slug` [@portal-app]. Unlike the admin shell, portal routes are path-based because public URLs need stable, shareable record and page addresses [@portal-app]. `/objects/:id` is the only route imported through `React.lazy()`: it is the sole path to `IIIFViewer` and its `@samvera/clover-iiif` + `openseadragon` dependency, so Vite ships that viewer chunk only when a record detail page is opened instead of bundling it into every other route (see [Media And IIIF](../workflows/media-and-iiif)) [@portal-app].

The header provides admin-configurable type-scoped navigation links and a debounced autocomplete search. `browse_enabled_types` controls which public browse entries appear in the header; it hides an empty browsing entry without restricting public detail URLs. It preserves the current `type` query parameter when the user searches from a scoped page and maps search hits to the corresponding detail URL based on `record_type` [@portal-app] [@portal-api]. On mobile, the search input's relative-positioned wrapper, not only the form, expands to the full header width so the autocomplete dropdown keeps the same alignment boundary [@portal-app] [@portal-styles]. `SiteFooter` renders the configured `PortalConfig.footer`: up to six columns of type `text` (Markdown, sanitized through the same `renderMarkdown` helper as static pages), `links` (site-relative paths become router links, external URLs open in a new tab; optionally appended pages placed in the footer) or `logos` (image, alt text, optional link), plus a bottom line. Without columns and bottom text it keeps the built-in one-line footer with the published footer pages and the API link [@portal-app] [@pages-api]. The API accepts only http(s) URLs or site-relative paths for footer links and images; footer images can be uploaded via `POST /v1/portal/footer-assets` (raster images, no SVG) and are served from `/portal/v1/portal/footer-assets/<random name>` [@portal-api]. `UsageNotice` shows `PortalConfig.notice` once per browser and notice version (`localStorage` key `katalon_notice_v<version>`) as a modal dialog that moves focus to its button, keeps Tab inside and restores focus afterwards; raising the version in the admin shows it to everyone again [@usage-notice] [@footer-notice-settings]. The notice is a deployment-configured message, not a hardcoded compliance feature: the backend model stores an empty JSON object by default, `NoticeConfig.enabled` defaults to `false`, and title/text/button labels are ordinary multilingual settings edited in Admin [@portal-model] [@portal-api] [@footer-notice-settings]. With a logo, the header renders it as `<img>` (alt = site title when the title text is hidden by `header_show_title=false`) and `hero_hide_title` replaces the homepage title/subtitle by the logo [@portal-app].

## Public API Surface

The portal client sends an existing in-memory Katalon access token when one is present, refreshes it once after a `401`, and otherwise keeps anonymous-read semantics [@portal-client]. `/login` uses the existing `/v1/auth/token` endpoint; its host-only refresh cookie is also recognized by the Admin UI on the same origin when that application starts. A recognised staff role (`superuser`, `admin`, `editor`, `cataloger`, or `viewer`) receives internal records where its backend read permission allows them, plus all schema fields and internal search; a future public-account role remains on the anonymous projection [@portal-client] [@portal-public-api].

The backend confines this anonymous surface to the five public inventory record families. It has no Procedure or Storage Location endpoint, and it returns relations only where both endpoints are visible public inventory records. Its response models are public projections: they omit record versions and search vectors; relation responses omit relation metadata; and public responses return their own `/portal/v1` `_links` instead of the authenticated `/v1` links [@portal-public-api].

Backend portal config is stored as the singleton `portal_config` row with defaults for title, subtitle, hero text, featured object ids, homepage blocks, facet fields, result-subtitle fields, enabled browsing types, terminology overrides, accent color, logo URL, placeholder image URL, extra CSS color tokens, detail-sidebar position, and metadata-row layout [@portal-api]. The read endpoint applies those defaults before Pydantic response validation, so rows created before newer config columns existed still return a complete public config [@portal-api]. `GET /v1/portal/config` builds `facet_fields` dynamically from non-deleted `field_definitions` with `is_facet`, while `PUT /v1/portal/config` and logo upload require an admin role [@portal-api]. This makes search facets an effect of schema configuration rather than a separate portal-only list [@portal-api].

Static pages have a public list and public by-slug read path that only return `is_published` pages, plus admin-only CRUD paths that can see unpublished pages [@pages-api]. Static pages support attaching file assets (images, PDF documents, and MP4 videos; SVG is rejected for security), which are served publicly under `/portal/v1/pages/assets/:id/:filename` and can be embedded via Markdown snippets (`![]()` for images, PDF links, and `<video>` tags sanitized via DOMPurify). Banners have public active endpoints for admin and portal surfaces, filtered by active flag, expiration, and surface visibility; banner CRUD remains admin-only [@banners-api].

## Record Detail Layout

Object, Entity, Place, Occurrence, and Collection detail pages share the same public projection rules. The four non-collection detail pages share `DetailPageLayout`; Collection detail uses its own page for hierarchy, collection children, and member-object presentation [@detail-layout] [@portal-app] [@portal-public-api]. Public field definitions select the main column or metadata sidebar through `detail_slot`; one field per type or subtype can take the description role through `detail_role` [@detail-layout]. Group fields render inside their group, one line per entry ("sub-field: value", value only for single-sub-field groups); sub-fields are matched to their group through `parent_id` against the field `id` that the public schema endpoint exposes, and never render as top-level fields. The page-level `title`/`name` filter (`withoutTitleFields`) only drops top-level fields, because group sub-fields may legitimately be called `name` or `title`. Detail pages also keep only fields without a subtype or with the record's own subtype (`fieldsForSubtype`, fed by `target_subtype` from the public schema), so equally named fields of different subtypes never mix. A group with the setting `emphasize_first_child` renders the value of its first sub-field bold in every entry. Collection detail uses the same row via `GroupMetaRow` [@detail-layout]. The entity/occurrence type tag resolves the admin-configured subtype label (scoped to the record type) before the built-in translation, matching search results.

Detail-page presentation has a small admin-owned configuration surface rather than a separate theme contract. `ScreenSettings` saves `detail_sidebar_position`, `meta_row_layout`, `meta_label_uppercase`, and visual tokens through `/v1/portal/config`; the Portal reads the same config through its public client after loading the file-based theme layer [@admin-settings] [@portal-api] [@portal-client] [@portal-app]. `detail_sidebar_position` places the narrow sidebar left or right, `meta_row_layout` toggles each metadata row between label-above-value (default) and inline "label: value" via the `.detail-meta--inline` CSS class, and the inline variant uses a fixed-width label column without row hairlines [@detail-layout] [@portal-styles]. `meta_label_uppercase` is a boolean defaulting off; on the normal detail wrapper it adds `.detail-layout--caps`, which capitalizes metadata and relation labels [@detail-layout] [@portal-styles]. Pages without main-column content collapse to one bounded metadata column [@detail-layout].

## Runtime Theme Layers

Route changes to another path scroll to the top (`components/ScrollToTop.tsx`, mounted once in `App.tsx`); query-only changes such as search filters keep the scroll position, and back/forward navigation (`POP`) is left to the browser's scroll restoration. Themes no longer need to wrap `history.pushState` for this.

The IIIF viewer (Clover), media player and media thumbnails take their dark stage colour from the theme token `--viewer-bg` (default `#0f172a`; Clover receives it as `options.background`, which it writes into `--clover-viewer-background`), and `styles.css` maps Clover's `--clover-color-accent` to the theme `--accent` on `:root`, so navigator frame and active page follow the theme [@detail-layout].

Theme tokens and the theme stylesheet reach the browser before the first paint: `GET /portal/v1/theme.css` renders an `@import` of the manifest's `fonts.body` stylesheet (same-origin path or `https` URL only) followed by one `:root:root` block with the default tokens, the manifest tokens and the portal-config overrides (`color_tokens`, then `accent_color` unless it is still the default `#1e3a8a`); token names and values that could leave the declaration are dropped [@theme-api]. A Vite plugin links that stylesheet at the end of `<head>`, after the app CSS, so it is render-blocking and theme rules win ties with the app styles [@portal-vite]. The portal still loads `/portal/v1/theme` at startup and passes the manifest to `applyTheme`, which only updates the favicon under `/themes/<file>` and adds an optional theme script (`theme.json` `"script"`) once as a deferred `<script src="/themes/<directory>/<script>">`; the API adds the theme `directory` and drops scripts that are not a plain `.js` path inside it, so the CSP `script-src 'self'` holds and no nginx `sub_filter` injection is needed [@theme-inject]. The configured portal `site_title` owns the visible portal brand and the Helmet title template, so a theme name cannot replace the institution's browser title [@portal-app] [@theme-inject] [@theme-loader].

`AppInner` reads portal config and passes configured terminology and supported languages into the portal i18n resolver; it no longer writes colour tokens itself [@portal-app] [@portal-i18n]. The visual order — default tokens, theme manifest tokens, then portal-config overrides — is fixed server-side in `theme.css`, which gives operators a persistent configuration layer without rebuilding the frontend and without a flash of the default colours [@theme-api]. For the two configuration decisions that changed this surface, see [Configurable Portal Homepage Blocks](../../decisions/frontend/configurable-portal-homepage) and [Configurable Portal Terminology](../../decisions/frontend/configurable-portal-terminology).

The routing frame connects to content workflows rather than owning them. Search pages and facet behavior depend on search endpoints, while record detail pages use media and IIIF data exposed by object endpoints. Those backend workflows are separate from this portal frame, but their public outputs are consumed through the portal client [@portal-client].
