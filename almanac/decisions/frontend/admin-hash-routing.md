---
title: "Admin Hash Routing"
summary: "The admin frontend uses URL hash state and central screen dispatch instead of React Router browser routes."
topics: [decisions, frontend, admin, routing]
sources:
  - id: app-shell
    type: file
    path: frontend/admin/src/components/layout/AppShell.tsx
  - id: sidebar
    type: file
    path: frontend/admin/src/components/layout/Sidebar.tsx
---

The admin app routes through the URL hash and a central `AppShell` switch instead of a browser router. `AppShell` parses `window.location.hash` into a route id and optional edit id, updates history with hash URLs, and renders each screen from a single dispatch function [@app-shell]. This decision keeps admin navigation inside the deployed shell while the sidebar remains a declarative list of route ids, labels, icons, active aliases, and role visibility rules [@sidebar].

## Context

The admin surface is not a public content site with deep route ownership in separate page modules. It is a protected workbench with list, form, schema, vocabulary, importer, audit, settings, user, page, OAI set, subtype, and banner screens selected by small string ids [@app-shell]. The sidebar already models navigation in those same ids, including aliases such as `list` plus `form` for one active item, and hides admin-only groups by checking the current token role [@sidebar].

The shell also owns cross-cutting UI state that should not be split across route components. It tracks login state, sidebar visibility, current breadcrumbs, document title, configured application title, and dirty-form state [@app-shell]. A browser router would still need those shell-level guards and labels, so the current design keeps route parsing next to the state it protects.

## Decision

Admin navigation is represented as hash strings such as `#list` and `#form/<id>`. `hashToState()` strips the leading hash, defaults an empty hash to `list`, and treats the first slash as the boundary between the route id and edit id [@app-shell]. `navigate()` sets React state and calls `window.history.pushState()` with the hash, while the `popstate` listener re-parses the current hash when history changes [@app-shell].

Screen ownership stays centralized. `renderScreen()` switches on the current route id and passes record type, selected id, back callbacks, save callbacks, and dirty-change callbacks into the matching screen [@app-shell]. The sidebar does not push URLs itself; it calls `setRoute()`, which `AppShell` wires to `safeNavigate()` [@sidebar] [@app-shell].

## Consequences

Adding an admin screen means adding one route id to the sidebar when it should be navigable, one crumb entry when it needs breadcrumbs, and one `renderScreen()` case when it has a component [@sidebar] [@app-shell]. That is intentionally direct; there is no nested route tree or route loader layer to update.

Dirty-form protection belongs to the shell. `safeNavigate()` checks a mutable dirty ref, asks for confirmation before leaving unsaved work, clears the dirty flag after accepted navigation, and closes the mobile sidebar [@app-shell]. Record forms participate by calling `onDirtyChange`, but they do not own global navigation policy [@app-shell].

This routing choice makes route ids an internal admin contract. Links from admin UI should use the shell's navigation callbacks or hashes that match `AppShell` cases, not browser paths. For the wider shell and client boundary, see [Admin Shell And API Client](../../architecture/frontend/admin-shell-and-api-client).
