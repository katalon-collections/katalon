---
type: Decision
title: API-Worker mit gemeinsamer Vorinitialisierung
description: Der Container initialisiert Defaults vor dem Uvicorn-Mehrprozessstart; Verbindungsbudgets bleiben pro Prozess begrenzt.
tags: [api, startup, deployment, performance]
timestamp: 2026-10-21T20:18:00Z
---

# Kontext

IIIF-Anfragen prüfen Medienfreigaben über die API. Mehr Prozesse können deren parallelen Durchsatz erhöhen. Die bisherige Lifespan-Initialisierung legt fehlende Defaults per Lesen und anschließendem Schreiben an; mehrere frische Worker könnten dabei konkurrieren und Erststart-Zugangsdaten entfernen.

# Entscheidung

Der API-Entrypoint führt nach Migrationen einmal `katalon.management.bootstrap` aus und markiert den erfolgreichen Abschluss für seine Kindprozesse. Worker prüfen weiter ihre Sicherheitsvoraussetzungen. Standard sind zwei Prozesse über Uvicorns vorhandene Variable `WEB_CONCURRENCY`; jeder hat im Image einen Pool von fünf plus fünf zusätzlichen Datenbankverbindungen. Host-Starts ohne Entrypoint bleiben bei einem Prozess. Mehrere unabhängige API-Container sind damit nicht koordiniert.

Normdaten-Registrierungen werden nach Laufzeitänderungen ohne unbefristeten Prozesscache gelesen. Der Exportformat-Katalog behält seinen Cache, da Änderungen dort direkte Datenbankpflege mit dokumentiertem Neustart voraussetzen.

# Begründung

Die Vorinitialisierung verhindert doppelte Schreibvorgänge ohne verteilte Lock-Infrastruktur für die aktuelle Ein-Container-Topologie. Uvicorns Standardvariable erspart einen zusätzlichen Alias. Medien-Identifier erhalten Datenbankindizes; nginx prüft weiterhin jede Freigabe frisch. Heapgröße und Memory-Locking bleiben Betreiberoptionen, weil verfügbarer RAM und Last pro Institution variieren.

# Citations

- `backend/docker-entrypoint.sh`
- `backend/src/katalon/management/bootstrap.py`
- `backend/src/katalon/main.py`
- `docker/Dockerfile.backend`
- `backend/tests/integration/test_api_workers.py`
- `docs/02_produktion.md`
