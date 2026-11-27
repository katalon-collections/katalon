---
type: Decision
title: Datumsangaben – ISO speichern, in Admin und Portal menschlich schreiben
description: Gespeichert wird ISO 8601 mit astronomischer Jahreszählung; Admin-Eingabe, Admin-Anzeige und Portal nutzen dieselbe Schreibweise.
tags: [metadata, admin, portal, i18n]
timestamp: 2026-11-26T10:00:00Z
---

# Kontext

Jahre vor Christus werden als `-0042` gespeichert (ISO 8601: Jahr `0000` = 1 v. Chr.). Das
Admin-Formular zeigte diesen Rohwert, das Portal „43 v. Chr.“. Erfassende lasen die Zahl als
Jahresangabe und sahen einen Versatz um ein Jahr.

# Entscheidung

- Speicherform, API, Import und Export bleiben ISO.
- Admin-Feld und Listenspalten zeigen dieselbe Form wie das Portal (`43 v. Chr.`, `ca. 1900`, `vor 1800`).
- Getippter Text läuft durch `parseDateText`; ein führendes Minus zählt dort wie im Sprachgebrauch
  (`-43` = 43 v. Chr.). Gespeicherte Werte durchlaufen diesen Parser nie, sonst verschöbe sich das
  Jahr bei jedem Speichern.

# Begründung

Abgelehnt: Speicherform auf historische Zählung ändern. Das hätte Bestandsdaten, Sortierung,
LIDO-Export und ISO-Konformität gebrochen. Abgelehnt: Rohwert mit Erklärtext im Admin; zwei
Schreibweisen für dasselbe Datum bleiben fehleranfällig.

# Citations

[1] frontend/admin/src/lib/dateInput.ts
[2] frontend/portal/src/utils/renderFieldValue.ts
