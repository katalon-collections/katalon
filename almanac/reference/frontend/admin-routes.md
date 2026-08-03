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
---

Admin routes are hash routes owned by `AppShell`, not browser paths. The shell parses `window.location.hash`, stores the route and optional edit id in React state, and renders one screen component from a `switch` over that route [@app-shell]. The sidebar is the visible navigation surface for most routes, groups admin-only configuration and user-management entries by role, and marks both list and form routes active through each item route set [@sidebar].

## Route Format

Admin URLs use `#route` for list and tool screens, and `#route/id` for edit screens. `hashToState` removes the leading hash, defaults an empty hash to `list`, and splits the first slash into `{ route, editId }` [@app-shell].

Navigation writes the same shape back to browser history. If an edit id is present, `navigate` writes `#<route>/<id>`; otherwise it writes `#<route>` [@app-shell].

## Content Routes

| Hash route | Screen | Record type | Sidebar entry |
|---|---|---:|---|
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

List screens receive an `onOpen` callback that navigates to the matching form route with the record id. Form screens receive a `recordId` only when the hash contains the `/id` suffix, so the same component handles create and edit states for each record type [@app-shell]. The form workflow behind these routes is covered by [Schema Driven Record Forms](../../architecture/workflows/schema-driven-record-forms).

## Configuration And Operations Routes

| Hash route | Screen | Access in render | Sidebar access |
|---|---|---|---|
| `#subtypes` | `ScreenSubtype` | admin or superuser | admin or superuser |
| `#schema` | `ScreenSchema` | any logged-in user | admin or superuser |
| `#form-variants` | `ScreenFormVariants` | admin or superuser | admin or superuser |
| `#vocab` | `ScreenVocab` | any logged-in user | admin or superuser |
| `#vocab/<name>` | `ScreenVocab` | any logged-in user | admin or superuser |
| `#pages` | `ScreenPages` | any logged-in user | admin or superuser |
| `#oai-sets` | `ScreenOAISets` | admin or superuser | admin or superuser |
| `#banners` | `ScreenBanners` | admin or superuser | admin or superuser |
| `#import` | `ScreenImporter` | any logged-in user | any logged-in user |
| `#audit` | `ScreenAudit` | any logged-in user | any logged-in user |
| `#users` | `ScreenUsers` | any logged-in user | admin or superuser |
| `#settings` | `ScreenSettings` | any logged-in user, with `isAdmin` prop | admin or superuser |

`AppShell` computes `isAdmin` from the decoded token role and uses it directly for `banners`, `subtypes`, and `oai-sets`; unauthorized users see a placeholder for those routes [@app-shell]. `Sidebar` separately hides configuration and management navigation items unless the current role is `admin` or `superuser` [@sidebar]. The shell and API-client responsibilities around login, route rendering, banners, and unauthorized handling are described in [Admin Shell And API Client](../../architecture/frontend/admin-shell-and-api-client).

## Navigation Guards

`safeNavigate` blocks sidebar and topbar navigation when a form has marked itself dirty and the user rejects the confirmation prompt. When navigation proceeds, it clears the dirty flag, closes the mobile sidebar, and delegates to `navigate` [@app-shell].

## Titles And Breadcrumbs

`CRUMBS` defines labels and parent routes for known hash routes. The shell replaces the first breadcrumb with the configured portal site title and derives `document.title` from the active route; `settings` is titled as the admin app root, while other known routes use the current breadcrumb label plus the admin suffix [@app-shell].
