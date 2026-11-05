---
title: "Admin Shell And API Client"
summary: "The admin frontend uses a small hash-routed shell around typed API modules that own authentication, refresh, conflicts, and record operations."
topics: [architecture, frontend, admin, api-client, authentication]
sources:
  - id: dashboard-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenDashboard.tsx
  - id: dashboard-service
    type: file
    path: backend/src/katalon/services/dashboard_service.py
  - id: app-shell
    type: file
    path: frontend/admin/src/components/layout/AppShell.tsx
  - id: sidebar
    type: file
    path: frontend/admin/src/components/layout/Sidebar.tsx
  - id: topbar
    type: file
    path: frontend/admin/src/components/layout/Topbar.tsx
  - id: user-roles-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenUserRoles.tsx
  - id: api-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: screen-login
    type: file
    path: frontend/admin/src/components/screens/ScreenLogin.tsx
  - id: admin-config-api
    type: file
    path: backend/src/katalon/api/v1/admin_config.py
  - id: changelog
    type: file
    path: CHANGELOG.md
  - id: vite-config
    type: file
    path: frontend/admin/vite.config.ts
  - id: form-copy-de
    type: file
    path: frontend/admin/src/i18n/locales/de/screenForm.json
  - id: form-copy-en
    type: file
    path: frontend/admin/src/i18n/locales/en/screenForm.json
---

The admin shell is a browser-only application frame that keeps route state in the URL hash, dispatches each route to a screen component, and delegates all HTTP behavior to a typed API client. `AppShell` owns login state, route parsing, breadcrumbs, dirty-form navigation guards, and screen selection, while `client.ts` owns token storage, automatic refresh, error normalization, and record-specific API wrappers [@app-shell] [@api-client]. This split matters because the screens can call domain modules such as `objects`, `entities`, `procedures`, `schema`, and `media` without repeating authentication or endpoint details [@api-client].

## Shell Boundary

`AppShell` initializes the admin state from `window.location.hash`, turns hashes such as `#form/<id>` into a `route` and optional `editId`, and updates history with `pushState` when a user navigates [@app-shell]. The shell does not use React Router; it uses a switch over route ids to render overview dashboard, list, form, schema, vocabulary, importer, audit, settings, user, role-matrix, static page, OAI set, subtype, and banner screens [@app-shell] [@user-roles-screen].

The sidebar is a declarative navigation list that maps ids to labels, icons, active-route aliases, and role restrictions [@sidebar]. Admin-only groups and items check the decoded token role before rendering, and `AppShell` repeats the same `admin`/`superuser` gate when rendering configuration, user-management, and roles routes so direct hash navigation cannot open those screens for lower roles [@sidebar] [@app-shell]. Backend endpoints still enforce permissions independently of this frontend gate [@api-client].

The sidebar footer shows only the product/version string, currently `Katalon Collections v{package.json version}`. Account actions live in the topbar user menu, where users can open account settings, change UI language, or log out; the sidebar no longer duplicates email, role, and logout controls [@sidebar] [@topbar].

The shell also loads `/v1/portal/config` to replace the default `Katalon` title with the configured site title, then uses that value for breadcrumbs and `document.title` [@app-shell]. That endpoint requires authentication, so the fetch runs only after `restoreSession()` completed and the shell switched to the logged-in state; firing it on mount would race the token refresh and log a guaranteed 401 on every reload [@app-shell]. The same shell renders admin banners and import-status banners above the current screen, so cross-cutting notices stay outside individual workflow screens [@app-shell].

## Overview Dashboard

`#dashboard` is the default logged-in route. Its summary groups recent edits, personal locks, working sets, upcoming procedure deadlines, team activity and draft counts, filtering record types by the user's read permissions. Administrators and users with the manual-lock feature also receive the all-locks section. The screen calls existing lock-release actions and stores section visibility in the browser; admin-only system health is fetched separately. The shared lock response model lives in `core.schemas`, so the dashboard service and lock API use the same shape without a service importing an API module [@dashboard-screen] [@dashboard-service].

## Routing And Unsaved State

Hash routing keeps the admin app deployable below a path prefix without server-side route rewrites. `safeNavigate` checks a mutable dirty-form ref, shows a browser confirmation when the current screen has unsaved changes, closes the mobile sidebar, and only then pushes the new hash [@app-shell]. [Schema Driven Record Forms](../workflows/schema-driven-record-forms) plugs into this by passing `onDirtyChange` from `ScreenForm` back to the shell [@app-shell]. Links from inside a record form to related records (relation-field chips, the relations panel, linked procedures/objects) bypass `safeNavigate`; `ScreenForm` guards them itself via `handleRecordLinkClick`, which reuses the form's own unsaved-changes modal and navigates to the target record after "discard". Modifier clicks open the target in a new tab without a prompt, and quick-create forms render these labels as plain text.

The Vite config keeps the frontend base path configurable through `VITE_BASE_PATH`, with `/` as the local default, and proxies `/v1` to the backend during development [@vite-config]. That makes the admin build sensitive to deployment prefix configuration even though runtime navigation itself is hash based [@vite-config].

## Interface Wording

Short form hints and placeholders use the German and English locale resources. Search placeholders name the action; save prerequisites explain what must be saved before the next action is available. Upload hints refer to media rather than only images. German prompts use the formal “Sie”; progress labels describe the action in progress [@form-copy-de] [@form-copy-en].

## API Client Contract

The admin API client keeps the access token only in memory, exposes `setToken`, `hasToken`, and `getTokenUser`, and lets the shell register an unauthorized callback [@api-client]. At startup it exchanges the host-only refresh cookie at `/v1/auth/refresh` for an access token; `authorizedFetch` retries one failed request through the same route and clears session state when refresh is rejected with `401` [@api-client].

The login screen also provides password-reset request and confirmation forms. Reset links use the `#reset-password?token=...` hash route, so they remain valid under the admin deployment prefix without server-side routing [@screen-login] [@api-client].

`req<T>` is the shared JSON request wrapper. It adds `Content-Type: application/json`, converts `401` into a session-expired error, converts delete conflicts into `ConflictError`, and converts stale optimistic-locking saves into `VersionConflictError` when the backend returns `detail.error == "version_conflict"` [@api-client]. The record modules then expose typed methods for list, get, audit, create, update, delete, publish or complete, snapshots, media, relations, static pages, banners, importer, OAI sets, API keys, settings, PID registration, and AI completion [@api-client].

The client sends `If-Match` whenever a loaded record version is available, which is always the case for the Admin form's update flow since it loads the record (and its version) before allowing a save; the backend now requires the header on every record update, publish, and snapshot-restore endpoint, returning `428` if it is absent [@api-client]. That same conflict surface is used by [Schema Driven Record Forms](../workflows/schema-driven-record-forms), while backend update behavior is covered by [Audit And Snapshots](../workflows/audit-and-snapshots) [@api-client].

Admin settings also expose the version notes through the authenticated `/v1/admin/config/changelog` endpoint. The endpoint reads the `CHANGELOG.md` bundled into the API image, so the notes shown after a deployment match that image's version [@admin-config-api] [@changelog].
