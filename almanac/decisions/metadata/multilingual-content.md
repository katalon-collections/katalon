---
title: "Multilingual Content"
summary: "Field labels and translatable text values use lang-keyed JSONB dicts driven by a configurable supported_languages list; the portal UI is internationalised with a dependency-free t()/useI18n module."
topics: [decisions, metadata, i18n, frontend, portal]
sources:
  - id: decision
    type: file
    path: .agents/knowledge/decisions/mehrsprachigkeit.md
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: schema-service
    type: file
    path: backend/src/katalon/services/schema_service.py
  - id: schema-admin
    type: file
    path: backend/src/katalon/api/v1/schema_admin.py
  - id: migration
    type: file
    path: backend/migrations/versions/0036_multilingual_content.py
  - id: i18n
    type: file
    path: frontend/portal/src/i18n/index.ts
  - id: label-editor
    type: file
    path: frontend/admin/src/components/ui/LabelEditor.tsx
  - id: translatable-input
    type: file
    path: frontend/admin/src/components/ui/TranslatableInput.tsx
  - id: importer-api
    type: file
    path: backend/src/katalon/api/v1/importer.py
  - id: importer-ui
    type: file
    path: frontend/admin/src/components/screens/importer/types.ts
---

Katalon separates multilingual *configuration* from multilingual *content*. Labels — field names, subtypes, form variants, vocabulary terms — are JSONB dicts shaped like `{"de": "...", "en": "..."}`. Record values for translatable fields use the same lang-keyed dict shape. The set of languages is global configuration, not per-field [@decision].

## Context

Labels had been hard-coded to a `de`/`en` pair: the admin UI rendered two fixed "Label DE"/"Label EN" inputs in five separate screens, and the importer wrote only those two keys. There was no way to translate a *value* (a "Beschreibung" field held one string), and the portal UI chrome was German-only with no i18n framework [@decision].

Issue #6 had scoped multilingual metadata earlier but was left as a closed concept; the concrete work took a deliberately smaller cut than that issue's seven-step plan [@decision].

## Decision

1. **`supported_languages`** is an ordered JSONB list on `AdminConfig`; the first entry is the primary/fallback language. Editable under Admin → Settings → Sprachen [@models].
2. **`is_translatable`** is a boolean column on `field_definitions`, restricted to `text` and `richtext`, non-repeatable, top-level fields. Schema validation rejects repeatable, non-text, and group sub-field combinations with a 422 [@schema-admin] [@models].
3. **Translatable values are `{lang: text}` dicts**, not the lang-tagged array from the closed #6 concept. The dict shape matches labels and encodes "one value per language" without colliding with repeatable arrays. `validate_metadata` enforces a dict of string values [@schema-service].
4. **Admin editing**: a shared `LabelEditor` loops over `supported_languages` for labels. `ScreenForm` renders a `TranslatableInput` for translatable fields — primary language always visible, a "+ XY" button reveals further languages, each added language gets a remove button [@label-editor] [@translatable-input].
5. **Portal UI i18n** is a dependency-free module (`de.ts`/`en.ts` dicts plus `useI18n` over `useSyncExternalStore` and a `t(key, params)` with `{param}` interpolation) — deliberately not `react-i18next`, which is overkill for the ~70-string catalog [@i18n].
6. **Language resolution**: `?lang=` → `localStorage` → `navigator.language` → primary. Portal field values and labels render in the active locale via `renderFieldValue(value, locale)` and `label[locale] ?? label.de ?? label.en` [@i18n].

## Consequences

Labels and translatable values now share one mental model: a JSONB dict keyed by the configured languages. Migration `0036` adds the two columns (`is_translatable`, `supported_languages`) additively [@migration]. Importer-created fields are the main remaining exception: the importer request and pending-field UI still expose `label_de` and `label_en`, then write only those two label keys when creating fields [@importer-api] [@importer-ui].

The design is intentionally bounded. Structured field types (relation, date, number, boolean, vocabulary, authority, PID) and repeatable fields are not translatable — they are language-independent. The primary `title`/`name` field stays single-valued, so it is not marked translatable. Search still indexes all language variants together; per-language analyzers were left out.

Adding a new language is a data/config change, not a schema change: extend `supported_languages` and add a portal locale dict. No new columns or migrations are required.
