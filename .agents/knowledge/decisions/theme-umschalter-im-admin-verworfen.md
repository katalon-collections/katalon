---
type: Decision
title: Kein Theme-Umschalter im Admin-UI
description: Portal-Theme bleibt reine Datei-/Env-Var-Konfiguration; kein Dropdown zum Wechseln zwischen installierten Themes aus der Admin-Oberfläche.
tags: [portal, theming, admin, scope]
timestamp: 2026-09-24T00:00:00Z
---

# Kontext

Für die Portalgestaltung wurde mehr Anpassbarkeit gewünscht
(z. B. Farbpalette je nach Sammlungstyp). Das bestehende Drop-in-Theme-System
(`themes/<name>/theme.json` + `custom.css`, aktiviert über `PORTAL_THEME` in
`.env`) deckt das bereits ab. Diskutiert wurde zusätzlich ein Admin-UI-Dropdown,
das zwischen mehreren auf dem Server abgelegten Themes umschaltet, ohne
Env-Var/Neustart.

Aufwandsschätzung dafür: `active_theme`-Feld in der bestehenden
`portal_config`-Tabelle, Endpoint zum Auflisten verfügbarer Theme-Manifeste,
`GET /v1/theme` liest DB vor Env-Var, Admin-UI-Dropdown in `ScreenSettings.tsx`
mit DE/EN-Strings. Technisch klein (~halber bis ganzer Tag), kein neues
Subsystem.

# Entscheidung

Kein Admin-UI-Umschalter. Theme-Wechsel bleibt Datei-Ablage auf dem Server +
`PORTAL_THEME`-Env-Var + Neustart, wie in
[`docs/04_anpassungen.md`](../../../docs/04_anpassungen.md) beschrieben.

# Begründung

Der unterstützte Workflow verwaltet ein Theme-Paket pro Installation über
Dateien und Backend-Konfiguration. Ein zusätzlicher Umschalter würde das
Auflisten und Aktivieren mehrerer installierter Pakete erfordern. Dafür war
zum Entscheidungszeitpunkt kein konkreter Einsatzfall festgelegt.
Die Entscheidung begrenzt den aktuellen Produktumfang; sie trifft keine
allgemeine Aussage darüber, wie viele Themes eine Institution benötigen kann.

# Nachtrag 2026-09-24

Diese Entscheidung betrifft nur das Umschalten zwischen kompletten,
dateibasierten Themes. Einzelne Layout-Details, die als konkretes
Nutzerfeedback auftauchen (hier: Metadaten "Label über Wert" vs.
"Label: Wert"), werden weiterhin als reguläre `portal_config`-Felder mit
Admin-UI-Steuerung umgesetzt — siehe `meta_row_layout` in
`backend/src/katalon/api/v1/portal.py`, analog zu `detail_sidebar_position`.
Kein Widerspruch: das ist eine Produkteinstellung wie jede andere
Portal-Konfiguration, kein Theme-Store.

# Citations

[1] `backend/src/katalon/api/v1/theme.py`
[2] `docs/04_anpassungen.md`
[3] `README.public.md` (Theme-System-Zeile mit Doku-Link)
[4] `backend/src/katalon/api/v1/portal.py` (`meta_row_layout`, Nachtrag)
