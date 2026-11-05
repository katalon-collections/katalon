---
type: Decision
title: "Configurable Portal Terminology"
tags: [architecture, documentation]
timestamp: 2026-10-30T00:00:00Z
origin: almanac/decisions/frontend/configurable-portal-terminology.md
consolidated: 2026-10-30
---

Portal-facing labels for the five browsable record types can be overridden per installation — e.g. "Werk"/"Werke" instead of "Objekt"/"Objekte" for a library, "Exponat" for a museum — without touching the internal `record_type` values, API routes, or permissions (Issue #373) [1] [3].

## Context

The portal already had a single terminology choke point: `typeLabel(type)` in `frontend/portal/src/i18n/index.ts` resolves a record type to its German/English display label, and `t('nav.objects')` etc. resolve the pluralized navigation labels, both backed by static `type.*`/`nav.*` message keys [3]. Every place in the portal that shows a record-type name — main navigation, search result badges, facet values, collection type badges, advanced-search relation targets — already routes through one of these two functions rather than hard-coding a string per component.

Different institutions use different vocabulary for the same underlying record types (a museum's "Exponate" vs. a library's "Publikationen" are both `object` rows), which the portal previously had no way to express beyond editing the DE/EN locale files in source.

## Decision

`PortalConfig` gained one JSONB column, `terminology`: a map from record type (`object`, `entity`, `place`, `occurrence`, `collection` — the portal's browsable set, matching `browse_enabled_types`) to a `{singular, plural}` pair, each itself a per-language string map [1]. Validation lives in the shared Pydantic model `TerminologyEntry` in `portal.py`, reusing the same `GET/PUT /v1/portal/config` endpoint pair as every other portal setting — no new routes [2].

Rather than threading a terminology lookup through every call site that shows a record-type name, the override is applied inside the two existing resolver functions themselves. `t(key)` and `typeLabel(type, {plural})` in `i18n/index.ts` first consult a small `TERMINOLOGY_KEYS` table mapping message keys (`type.object`, `nav.objects`, …) back to `(recordType, form)`, and return the configured override for the active locale if one exists, falling back to the static default message otherwise [3]. `setTerminology()` (called once from `AppInner`'s portal-config load, alongside the existing `setSupportedLocales()`) stores the override map at module scope [4]. Because the config usually resolves after the header has mounted, `setTerminology()` must trigger a re-render: `useI18n()` subscribes via `useSyncExternalStore` to a revision counter that every change (locale, supported locales, terminology) bumps. Using the locale itself as snapshot was a bug — a terminology update left it unchanged, React skipped the re-render and the desktop header kept the default labels (covered by `i18n/index.test.tsx`) [3]. Because every existing call site already goes through `t()` or `typeLabel()`, none of them needed to change — the override became active everywhere a record-type label appears (navigation, homepage collection block, search result badges, facet values, collection type badges, advanced-search relation targets) as a side effect of this one change, not through a separate pass rewriting each component.

The admin UI adds a "Terminologie" section next to "Startseite" and "Portal & Institution", one card per record type with four inputs (singular/plural × DE/EN) and a "reset to default" button that clears that type's entry from the saved map, causing it to fall back to the built-in default on next load [5].

## Consequences

Existing installations get the new `terminology` column as non-null JSONB with an empty object default, so an upgrade preserves the previous labels until an admin saves overrides [6].

Unmapped types (`procedure`, `storage_location`, `vocabulary_term`) are not configurable through this feature — `typeLabel()` still falls back to the raw type string for them, matching pre-existing behavior, since they are not part of the portal's public browsable set.

This does not yet cover free-standing UI copy that mentions a record type inside a full sentence (e.g. a hypothetical "View all Works" button) rather than through a `t('nav.*')`/`typeLabel()` call — no such strings existed in the portal at the time of this change. Adding one later should route through the same resolver rather than hard-coding the type name, to stay consistent.

Compatible with the portal's existing multi-language support: overrides are stored per language key and read back using the same locale-with-fallback logic as the rest of `i18n/index.ts` [3]. Building on this, [Configurable Portal Homepage Blocks](../../../almanac/decisions/frontend/configurable-portal-homepage.md) already benefits without changes — its `collections` block's default heading falls through to `t('nav.collections')`, which is now terminology-aware.

# Citations

[1] backend/src/katalon/core/models.py
[2] backend/src/katalon/api/v1/portal.py
[3] frontend/portal/src/i18n/index.ts
[4] frontend/portal/src/App.tsx
[5] frontend/admin/src/components/screens/ScreenSettings.tsx
[6] backend/migrations/versions/0065_portal_config_terminology.py
