---
type: Decision
title: Lizenz AGPL-3.0-or-later + externes Branding "Katalon Collections"
description: SPDX-Header + AGPL-3.0-or-later auf allen Code-Dateien; extern heißt die Software "Katalon Collections" (Abgrenzung zu katalon.com), intern bleibt "Katalon".
tags: [lizenz, branding, legal]
timestamp: 2026-09-01T15:40:00Z
---

# Kontext

Die ursprüngliche README nannte MIT, während eine Lizenzdatei fehlte. Benötigt
wurde eine eindeutige Lizenz für das Open-Source-Projekt. Ziel ist, den
Quellcode und seine Weiterentwicklung unter festgelegten Weitergabebedingungen
zugänglich zu halten. Der Produktname musste außerdem vom unabhängigen
Test-Automatisierungsprodukt katalon.com abgegrenzt werden.

# Entscheidung

Das Projekt verwendet **AGPL-3.0-or-later**. Eine permissive MIT-Lizenz und BSL
wurden als Alternativen betrachtet; gewählt wurde die AGPL als Copyleft-Lizenz
für die gewünschte offene Weiterentwicklung. Maßgeblich für Rechte und Pflichten
ist der Lizenztext in `LICENSE`, nicht eine verkürzte Beschreibung hier.

Code-Dateien unter `backend/src`, `backend/tests`, `frontend/admin/src`,
`frontend/portal/src` und `e2e` tragen SPDX-Header und den Copyright-Vermerk
`Copyright (c) 2026 Karl Krägelin`.

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
die sichtbare Produktbezeichnung wird über UI und README vermittelt.

# Citations

[1] `almanac/decisions/operations/license-and-branding.md`
[2] `LICENSE`, `README.md`
[3] Lizenz- und Branding-Festlegung vom 2026-09-01
