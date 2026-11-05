---
title: "Admin Routes"
summary: "Reference for Admin hash routes, their screen components, and the record types they operate on."
topics: [reference, frontend, routing, admin]
sources:
  - id: app-shell
    type: file
    path: frontend/admin/src/components/layout/AppShell.tsx
  - id: sidebar
    type: file
    path: frontend/admin/src/components/layout/Sidebar.tsx
  - id: topbar
    type: file
    path: frontend/admin/src/components/layout/Topbar.tsx
  - id: docs-repo
    type: web
    url: https://github.com/katalon-collections/katalon-docs
  - id: docs-pages
    type: web
    url: https://katalon-collections.github.io/katalon-docs/
  - id: user-roles-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenUserRoles.tsx
  - id: storage-location-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenStorageLocation.tsx
  - id: users-api
    type: file
    path: backend/src/katalon/api/v1/users.py
---

Admin routes are hash routes owned by `AppShell`, not browser paths. The shell parses `window.location.hash`, stores the route and optional edit id in React state, and renders one screen component from a `switch` over that route [@app-shell]. The sidebar is the visible navigation surface for most routes, groups admin-only configuration and user-management entries by role, and marks both list and form routes active through each item route set [@sidebar].

## Route Format

Admin URLs use `#route` for list and tool screens, and `#route/id` for edit screens. `hashToState` removes the leading hash, defaults an empty hash to `dashboard`, and splits the first slash into `{ route, editId }` [@app-shell].

Navigation writes the same shape back to browser history. If an edit id is present, `navigate` writes `#<route>/<id>`; otherwise it writes `#<route>` [@app-shell].

The header search can create the same deep links for matched configuration entries: vocabulary and static-page results open the named item, while schema fields, subtypes, and form variants open their corresponding type scope. Settings sections use `#settings/<section>` [@topbar].

## Content Routes

| Hash route | Screen | Record type | Sidebar entry |
|---|---|---:|---|
| `#dashboard` | `ScreenDashboard` | — | Übersicht |
| `#list` | `ScreenList` | `object` | Objekte |
| `#form` | `ScreenForm` | `object` | Objekte |
| `#form/<id>` | `ScreenForm` | `object` | Objekte |
| `#entities-list` | `ScreenList` | `entity` | Entitäten |
| `#entities-form` | `ScreenForm` | `entity` | Entitäten |
| `#entities-form/<id>` | `ScreenForm` | `entity` | Entitäten |
| `#places-list` | `ScreenList` | `place` | Orte |
| `#places-form` | `ScreenForm` | `place` | Orte |
| `#places-form/<id>` | `ScreenForm` | `place` | Orte |
| `#occurrences-list` | `ScreenList` | `occurrence` | Occurrences |
| `#occurrences-form` | `ScreenForm` | `occurrence` | Occurrences |
| `#occurrences-form/<id>` | `ScreenForm` | `occurrence` | Occurrences |
| `#procedures-list` | `ScreenList` | `procedure` | Vorgänge |
| `#procedures-form` | `ScreenForm` | `procedure` | Vorgänge |
| `#procedures-form/<id>` | `ScreenForm` | `procedure` | Vorgänge |
| `#collections-list` | `ScreenList` | `collection` | Sammlungen |
| `#collections-form` | `ScreenForm` | `collection` | Sammlungen |
| `#collections-form/<id>` | `ScreenForm` | `collection` | Sammlungen |

List screens receive an `onOpen` callback that navigates to the matching form route with the record id. The primary label in each result row triggers that callback directly; the row's action menu remains available for edit/view and deletion. Form screens receive a `recordId` only when the hash contains the `/id` suffix, so the same component handles create and edit states for each record type [@app-shell]. The form workflow behind these routes is covered by [Schema Driven Record Forms](../../architecture/workflows/schema-driven-record-forms).

## Configuration And Operations Routes

| Hash route | Screen | Access in render | Sidebar access |
|---|---|---|---|
| `#subtypes` | `ScreenSubtype` | admin or superuser | admin or superuser |
| `#schema` | `ScreenSchema` | admin or superuser | admin or superuser |
| `#form-variants` | `ScreenFormVariants` | admin or superuser | admin or superuser |
| `#vocab` | `ScreenVocab` | admin or superuser | admin or superuser |
| `#vocab/<name>` | `ScreenVocab` | admin or superuser | admin or superuser |
| `#storage-locations` | `ScreenStorageLocation` | feature `storage_locations` | feature `storage_locations` |
| `#storage-locations/<id>` | `ScreenStorageLocation` | feature `storage_locations` | feature `storage_locations` |
| `#pages` | `ScreenPages` | admin or superuser | admin or superuser |
| `#oai-sets` | `ScreenOAISets` | admin or superuser | admin or superuser |
| `#export` | `ScreenExport` | feature `export` | feature `export` |
| `#sparql` | `ScreenSparql` | feature `sparql` and enabled SPARQL status | feature `sparql` and enabled SPARQL status |
| `#banners` | `ScreenBanners` | admin or superuser | admin or superuser |
| `#import` | `ScreenImporter` | any logged-in user | any logged-in user |
| `#audit` | `ScreenAudit` | any logged-in user | any logged-in user |
| `#working-sets` | `ScreenWorkingSets` | feature `working_sets` | feature `working_sets` |
| `#working-sets/<id>` | `ScreenWorkingSets` | feature `working_sets` | feature `working_sets` |
| `#users` | `ScreenUsers` | admin or superuser | admin or superuser |
| `#user-roles` | `ScreenUserRoles` | admin or superuser | not in sidebar; opened from `#users` |
| `#settings` | `ScreenSettings` | any logged-in user, with `isAdmin` prop | admin or superuser |

`AppShell` computes `isAdmin` from the decoded token role and uses it directly for `subtypes`, `schema`, `form-variants`, `users`, and `user-roles`; unauthorized users see a placeholder for those routes [@app-shell]. Other configuration screens are feature-gated from the token feature list, including `banners`, `vocab`, `pages`, `oai-sets`, `export`, `sparql`, and `working-sets`; the sidebar hides those entries with the same feature checks, with an additional live SPARQL status check before showing `#sparql` [@app-shell] [@sidebar]. The `#user-roles` screen is a separate roles-rights matrix opened from the user-management screen, not a primary sidebar item [@app-shell] [@user-roles-screen]. The shell and API-client responsibilities around login, route rendering, banners, and unauthorized handling are described in [Admin Shell And API Client](../../architecture/frontend/admin-shell-and-api-client).

Record delete controls are driven by `GET /v1/users/me/record-permissions`, which returns only the authenticated user's effective per-type actions; authorization remains enforced by the endpoint itself [@users-api]. The storage-location screen additionally exposes an admin-only trash switch. It lists deleted locations and offers restoration or irreversible purge without placing deleted nodes back into the editable hierarchy [@storage-location-screen].

## Navigation Guards

`safeNavigate` blocks sidebar and topbar navigation when a form has marked itself dirty and the user rejects the confirmation prompt. When navigation proceeds, it clears the dirty flag, closes the mobile sidebar, and delegates to `navigate` [@app-shell].

## Titles And Breadcrumbs

`CRUMBS` defines labels and parent routes for known hash routes. The shell replaces the first breadcrumb with the configured portal site title and derives `document.title` from the active route; `settings` is titled as the admin app root, while other known routes use the current breadcrumb label plus the admin suffix [@app-shell].

## Help Links

`Topbar` maps most hash routes to screen-specific documentation on the published GitHub Pages docs site [@topbar] [@docs-pages]:

- `schema` → `/administration/schema/`, `import` → `/administration/import/`, `form-variants` → `/administration/formularvarianten/`, `subtypes` → `/administration/subtypen/`, `storage-locations` → `/administration/lagerorte/`.
- All six record-list routes (`list`, `entities-list`, `places-list`, `occurrences-list`, `procedures-list`, `collections-list`) open `/administration/batch-bearbeitung/` — see [Batch Editing](../../workflows/batch-editing). `collections-form` opens `/administration/sammlungen/` and `procedures-form` opens `/reference/procedures/`; the remaining record-form routes (`form`, `entities-form`, `places-form`, `occurrences-form`) have no dedicated per-type page and fall back to the docs root.
- `users` and `user-roles` → `/administration/benutzer-und-rollen/`.
- `vocab` → `/administration/vokabulare/`, `pages` → `/administration/statische-seiten/`, `banners` → `/administration/banner/`, `audit` → `/administration/audit-log/`, `working-sets` → `/administration/arbeitslisten/`, `settings` → `/administration/einstellungen/`.
- `oai-sets` → `/integration/oai-pmh/`, `export` → `/integration/export-mappings/`, `sparql` → `/integration/sparql/`.

Routes without a `ROUTE_DOCS` entry fall back to the GitHub Pages docs root when the help icon is clicked [@topbar] [@docs-pages]. The public docs source repository lives at `katalon-collections/katalon-docs`, but the Admin help surface points users to the rendered Pages site rather than Markdown blobs [@docs-repo] [@docs-pages] [@topbar].
