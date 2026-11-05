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
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/admin-hash-routing.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/admin-hash-routing.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


The admin app routes through the URL hash and a central `AppShell` switch instead of a browser router. `AppShell` parses `window.location.hash` into a route id and optional edit id, updates history with hash URLs, and renders each screen from a single dispatch function [@app-shell]. This decision keeps admin navigation inside the deployed shell while the sidebar remains a declarative list of route ids, labels, icons, active aliases, and role visibility rules [@sidebar].


## Current Contract

Admin navigation is represented as hash strings such as `#list` and `#form/<id>`. `hashToState()` strips the leading hash, defaults an empty hash to `list`, and treats the first slash as the boundary between the route id and edit id [@app-shell]. `navigate()` sets React state and calls `window.history.pushState()` with the hash, while the `popstate` listener re-parses the current hash when history changes [@app-shell].

Screen ownership stays centralized. `renderScreen()` switches on the current route id and passes record type, selected id, back callbacks, save callbacks, and dirty-change callbacks into the matching screen [@app-shell]. The sidebar does not push URLs itself; it calls `setRoute()`, which `AppShell` wires to `safeNavigate()` [@sidebar] [@app-shell].

## Implementation Constraints

Adding an admin screen means adding one route id to the sidebar when it should be navigable, one crumb entry when it needs breadcrumbs, and one `renderScreen()` case when it has a component [@sidebar] [@app-shell]. That is intentionally direct; there is no nested route tree or route loader layer to update.

Dirty-form protection belongs to the shell. `safeNavigate()` checks a mutable dirty ref, asks for confirmation before leaving unsaved work, clears the dirty flag after accepted navigation, and closes the mobile sidebar [@app-shell]. Record forms participate by calling `onDirtyChange`, but they do not own global navigation policy [@app-shell]. The exception are in-form links to related records: `ScreenForm` pushes their hash directly and therefore checks its own dirty state before doing so (`handleRecordLinkClick`).

This routing choice makes route ids an internal admin contract. Links from admin UI should use the shell's navigation callbacks or hashes that match `AppShell` cases, not browser paths. For the wider shell and client boundary, see [Admin Shell And API Client](../../architecture/frontend/admin-shell-and-api-client).
