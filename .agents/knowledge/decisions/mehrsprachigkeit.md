---
type: Decision
title: Mehrsprachigkeit — konfigurierbare Sprachliste, übersetzbare Textfelder, Portal-UI-i18n
description: "Drei Ebenen: (1) Label-Dict statt hartkodiertem de/en, (2) is_translatable-Flag + {lang: text}-Dict für Feldwerte, (3) leichtgewichtiges Portal-i18n ohne Framework."
tags: [i18n, datenmodell, schema, frontend, portal]
timestamp: 2026-08-17T00:00:00Z
---

# Kontext

Drei getrennte Lücken bestanden gleichzeitig:

1. **Labels** waren hartkodiert als zwei feste Felder `label_de`/`label_en`
   in acht Admin-Dateien (ScreenSchema, ScreenSubtype,
   ScreenFormVariants, ScreenVocab, Importer). Es gab keine
   konfigurierbare Sprachliste; „eine weitere Sprache hinzufügen" hieß
   Code-Umbau.
2. **Feldwerte** hatten keine mehrsprachige Darstellung — ein Feld wie
   „Beschreibung" hielt genau einen String. Das Konzept in Issue #6
   (Option A, lang-getaggte Arrays) war nur als geschlossenes Dokument
   vorhanden, nicht implementiert.
3. **Portal-UI** war komplett deutsch-only, ohne i18n-Framework und ohne
   Sprachumschalter.

# Entscheidung

**Ebene 1 — Sprachliste.** Neues `supported_languages` (geordnete
JSONB-Liste) auf `AdminConfig`, erste Sprache = Primärsprache/Fallback.
Editierbar unter Einstellungen → Sprachen. Zusätzlich öffentlich über
`PortalConfigRead` exponiert, damit Portal und Nicht-Admin-Nutzer die
Liste ohne Admin-Recht lesen.

**Ebene 2 — Labels.** Hartkodiertes `label_de`/`label_en` ersetzt durch
eine wiederverwendbare `LabelEditor`-Komponente, die über
`supported_languages` iteriert. Backend-Modell blieb unverändert
(`label` war bereits JSONB-Dict).

**Ebene 3 — Feldwerte.** Neues Boolean `is_translatable` auf
`field_definitions` (Migration 0036), bewusst beschränkt auf
`text`/`richtext`, nicht wiederholbar, keine Container-Unterfelder
(Schema-Validierung → 422). Übersetzbarer Wert ist ein **`{lang: text}`-
Dict** — *nicht* das lang-getaggte Array aus #6. Begründung: konsistent
mit dem bestehenden `label`-Format, eindeutig „ein Wert pro Sprache",
kollidiert nicht mit wiederholbaren Arrays. `validate_metadata` erzwingt
ein Dict aus String-Werten.

**Ebene 4 — Portal-UI-i18n.** Eigenes, dependency-freies Modul
(`locales/de.ts` + `en.ts` + `useI18n` über `useSyncExternalStore`,
`t(key, {param})` mit Interpolation) statt `react-i18next` — bei ~70
Strings ist ein Framework Overkill. Sprachwahl-Reihenfolge: `?lang=` →
`localStorage` → `navigator.language` → Primärsprache. Portal rendert
Labels und übersetzbare Werte in der aktiven Locale
(`renderFieldValue(value, locale)`, `label[locale] ?? label.de ?? label.en`).

# Begründung

- **Dict statt Array** vermeidet eine zweite Darstellung desselben
  Konzepts (`label` ist bereits ein Dict) und hält „ein Wert pro
  Sprache" eindeutig von der Wiederholbarkeit getrennt.
- **Beschränkung auf Text/Rich-Text** hält strukturierte Feldtypen
  sprachunabhängig; Relation/Datum/Zahl/Boolean/Vokabular sind inhärent
  nicht übersetzbar.
- **Leichtgewichtiges i18n** statt Framework folgt dem
  kleinstmöglichen-Eingriff-Prinzip; eine neue Sprache = Sprachliste
  erweitern + Locale-Datei kopieren, kein Schema-Change.

# Citations

[1] `backend/migrations/versions/0036_multilingual_content.py`
[2] `backend/src/katalon/services/schema_service.py` (`validate_metadata`)
[3] `backend/src/katalon/api/v1/schema_admin.py` (`_validate_field_settings`)
[4] `frontend/portal/src/i18n/index.ts`
[5] Issue #6 (geschlossenes Konzept Mehrsprachigkeit)
