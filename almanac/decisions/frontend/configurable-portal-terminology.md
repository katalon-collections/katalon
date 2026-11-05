---
title: "Configurable Portal Terminology"
summary: "Portal record-type labels (object, entity, place, occurrence, collection) are overridable per installation, resolved centrally through the existing i18n layer."
topics: [decisions, frontend, portal]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: portal-api
    type: file
    path: backend/src/katalon/api/v1/portal.py
  - id: portal-i18n
    type: file
    path: frontend/portal/src/i18n/index.ts
  - id: portal-app
    type: file
    path: frontend/portal/src/App.tsx
  - id: settings-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: migration
    type: file
    path: backend/migrations/versions/0065_portal_config_terminology.py
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/configurable-portal-terminology.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/configurable-portal-terminology.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Portal-facing labels for the five browsable record types can be overridden per installation — e.g. "Werk"/"Werke" instead of "Objekt"/"Objekte" for a library, "Exponat" for a museum — without touching the internal `record_type` values, API routes, or permissions (Issue #373) [@models] [@portal-i18n].


## Current Contract

`PortalConfig` gained one JSONB column, `terminology`: a map from record type (`object`, `entity`, `place`, `occurrence`, `collection` — the portal's browsable set, matching `browse_enabled_types`) to a `{singular, plural}` pair, each itself a per-language string map [@models]. Validation lives in the shared Pydantic model `TerminologyEntry` in `portal.py`, reusing the same `GET/PUT /v1/portal/config` endpoint pair as every other portal setting — no new routes [@portal-api].

Rather than threading a terminology lookup through every call site that shows a record-type name, the override is applied inside the two existing resolver functions themselves. `t(key)` and `typeLabel(type, {plural})` in `i18n/index.ts` first consult a small `TERMINOLOGY_KEYS` table mapping message keys (`type.object`, `nav.objects`, …) back to `(recordType, form)`, and return the configured override for the active locale if one exists, falling back to the static default message otherwise [@portal-i18n]. `setTerminology()` (called once from `AppInner`'s portal-config load, alongside the existing `setSupportedLocales()`) stores the override map at module scope [@portal-app]. Because the config usually resolves after the header has mounted, `setTerminology()` must trigger a re-render: `useI18n()` subscribes via `useSyncExternalStore` to a revision counter that every change (locale, supported locales, terminology) bumps. Using the locale itself as snapshot was a bug — a terminology update left it unchanged, React skipped the re-render and the desktop header kept the default labels (covered by `i18n/index.test.tsx`) [@portal-i18n]. Because every existing call site already goes through `t()` or `typeLabel()`, none of them needed to change — the override became active everywhere a record-type label appears (navigation, homepage collection block, search result badges, facet values, collection type badges, advanced-search relation targets) as a side effect of this one change, not through a separate pass rewriting each component.

The admin UI adds a "Terminologie" section next to "Startseite" and "Portal & Institution", one card per record type with four inputs (singular/plural × DE/EN) and a "reset to default" button that clears that type's entry from the saved map, causing it to fall back to the built-in default on next load [@settings-screen].

## Implementation Constraints

Existing installations get the new `terminology` column as non-null JSONB with an empty object default, so an upgrade preserves the previous labels until an admin saves overrides [@migration].

Unmapped types (`procedure`, `storage_location`, `vocabulary_term`) are not configurable through this feature — `typeLabel()` still falls back to the raw type string for them, matching pre-existing behavior, since they are not part of the portal's public browsable set.

This does not yet cover free-standing UI copy that mentions a record type inside a full sentence (e.g. a hypothetical "View all Works" button) rather than through a `t('nav.*')`/`typeLabel()` call — no such strings existed in the portal at the time of this change. Adding one later should route through the same resolver rather than hard-coding the type name, to stay consistent.

Compatible with the portal's existing multi-language support: overrides are stored per language key and read back using the same locale-with-fallback logic as the rest of `i18n/index.ts` [@portal-i18n]. Building on this, [Configurable Portal Homepage Blocks](configurable-portal-homepage) already benefits without changes — its `collections` block's default heading falls through to `t('nav.collections')`, which is now terminology-aware.
