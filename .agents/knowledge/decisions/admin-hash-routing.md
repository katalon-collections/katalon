---
type: Decision
title: "Admin Hash Routing"
tags: [architecture, documentation]
timestamp: 2026-10-30T00:00:00Z
origin: almanac/decisions/frontend/admin-hash-routing.md
consolidated: 2026-10-30
---

The admin app routes through the URL hash and a central `AppShell` switch instead of a browser router. `AppShell` parses `window.location.hash` into a route id and optional edit id, updates history with hash URLs, and renders each screen from a single dispatch function [1]. This decision keeps admin navigation inside the deployed shell while the sidebar remains a declarative list of route ids, labels, icons, active aliases, and role visibility rules [2].

## Context

The admin surface is not a public content site with deep route ownership in separate page modules. It is a protected workbench with list, form, schema, vocabulary, importer, audit, settings, user, page, OAI set, subtype, and banner screens selected by small string ids [1]. The sidebar already models navigation in those same ids, including aliases such as `list` plus `form` for one active item, and hides admin-only groups by checking the current token role [2].

The shell also owns cross-cutting UI state that should not be split across route components. It tracks login state, sidebar visibility, current breadcrumbs, document title, configured application title, and dirty-form state [1]. A browser router would still need those shell-level guards and labels, so the current design keeps route parsing next to the state it protects.

## Decision

Admin navigation is represented as hash strings such as `#list` and `#form/<id>`. `hashToState()` strips the leading hash, defaults an empty hash to `list`, and treats the first slash as the boundary between the route id and edit id [1]. `navigate()` sets React state and calls `window.history.pushState()` with the hash, while the `popstate` listener re-parses the current hash when history changes [1].

Screen ownership stays centralized. `renderScreen()` switches on the current route id and passes record type, selected id, back callbacks, save callbacks, and dirty-change callbacks into the matching screen [1]. The sidebar does not push URLs itself; it calls `setRoute()`, which `AppShell` wires to `safeNavigate()` [2] [1].

## Consequences

Adding an admin screen means adding one route id to the sidebar when it should be navigable, one crumb entry when it needs breadcrumbs, and one `renderScreen()` case when it has a component [2] [1]. That is intentionally direct; there is no nested route tree or route loader layer to update.

Dirty-form protection belongs to the shell. `safeNavigate()` checks a mutable dirty ref, asks for confirmation before leaving unsaved work, clears the dirty flag after accepted navigation, and closes the mobile sidebar [1]. Record forms participate by calling `onDirtyChange`, but they do not own global navigation policy [1]. The exception are in-form links to related records: `ScreenForm` pushes their hash directly and therefore checks its own dirty state before doing so (`handleRecordLinkClick`).

This routing choice makes route ids an internal admin contract. Links from admin UI should use the shell's navigation callbacks or hashes that match `AppShell` cases, not browser paths. For the wider shell and client boundary, see [Admin Shell And API Client](../../../almanac/architecture/frontend/admin-shell-and-api-client.md).

# Citations

[1] frontend/admin/src/components/layout/AppShell.tsx
[2] frontend/admin/src/components/layout/Sidebar.tsx
