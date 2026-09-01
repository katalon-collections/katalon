---
type: Decision
title: Lizenz AGPL-3.0-or-later + externes Branding "Katalon Collections"
description: SPDX-Header + AGPL-3.0-or-later auf allen Code-Dateien; extern heißt die Software "Katalon Collections" (Abgrenzung zu katalon.com), intern bleibt "Katalon".
tags: [lizenz, branding, legal]
timestamp: 2026-09-01T15:40:00Z
---

# Kontext

Bisher hatte das Repo keine Lizenz gesetzt (README nannte fälschlich "MIT",
keine LICENSE-Datei existierte). Karl wollte verhindern, dass jemand den
Code klaut und als eigenes closed-source Produkt verkauft, ohne das
"Open-Source MMS"-Ziel aus `CLAUDE.md` aufzugeben. Parallel dazu: der
Produktname "Katalon" kollidiert mit dem unabhängigen kommerziellen
Test-Automatisierungsprodukt katalon.com.

# Entscheidung

**Lizenz**: AGPL-3.0-or-later (nicht BSL, nicht MIT).

- Grund gegen BSL: kein OSI-Open-Source, scheidet bei
  GLAM-Ausschreibungen oft aus, eigener Lizenztext nötig, in der Praxis
  ohnehin nicht durchsetzbar ohne Anwalt.
- Grund für AGPL: CollectiveAccess (nächster Vergleichsmaßstab im
  GLAM-Sektor) ist selbst AGPL-3.0. Network-Use-Klausel verhindert
  closed-source SaaS-Forks, verhindert aber nicht Weiterverkauf des
  unveränderten Codes — das kann keine OSI-Lizenz.
- Alle Dateien unter `backend/src`, `backend/tests`,
  `frontend/admin/src`, `frontend/portal/src`, `e2e` haben SPDX-Header
  (`SPDX-License-Identifier: AGPL-3.0-or-later` +
  `Copyright (c) 2026 Karl Krägelin`). `LICENSE`-Datei im Repo-Root.

**Branding**: extern "Katalon Collections", intern "Katalon".

- Extern (Browser-Tab-Titel beider Frontends, Login-Screen, README-Titel,
  neue "Über Katalon"-Seite in `ScreenSettings.tsx`): "Katalon
  Collections".
- Intern (Python-Package `katalon`, npm-Pakete `katalon-admin`/
  `katalon-portal`, GitHub-Repo `karkraeg/Katalon`, Sidebar/Breadcrumbs
  in der Admin-UI, alle Doku-Dateien in diesem Repo): weiterhin kurz
  "Katalon". Keine Code-Identifier umbenannt.

# Begründung

Reine Namensänderung im Code (Package-Rename, Repo-Rename) wäre teuer und
würde bestehende Links/CI/Deploy-Konfiguration brechen, ohne den
eigentlichen Zweck (Abgrenzung zu katalon.com nach außen) zu erfüllen —
die sehen nur UI und README, nicht den Quellcode.

# Citations

[1] `almanac/decisions/operations/license-and-branding.md`
[2] `LICENSE`, `README.md`
[3] Session-Entscheidung 2026-09-01
