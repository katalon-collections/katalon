---
type: Decision
title: Gemeinsamer Readiness-Check für die aktiven Dienste
description: /health bewertet DB, Suche, Redis, Worker-Heartbeat, Cantaloupe und optional Oxigraph; Versionsschutz und Broker-Fehlerbehandlung sind separate Verträge.
tags: [ops, health, resilience]
timestamp: 2026-07-13T05:14:00Z
---

# Kontext

Ein statisches OK erkennt Ausfälle der für Suche, Medien und Hintergrundarbeit
nötigen Dienste nicht. Der Compose-Betrieb benötigt einen gemeinsamen
Readiness-Status, während die Diagnose bei den Dienstlogs bleibt.

# Entscheidung

`/health` prüft PostgreSQL, Elasticsearch, Redis, den Beat-/Worker-Heartbeat,
Cantaloupe und bei Aktivierung Oxigraph. Jeder aktive fehlgeschlagene Check
führt zu `503` und `status: degraded`. Queue-Länge und Backup-Alter sind
informativ und beeinflussen den Statuscode nicht.

Ein Gesamtstatus darf degradiert sein, obwohl einzelne REST-Schreibpfade
weiter funktionieren. [Broker-tolerantes Enqueue](broker-tolerant-enqueue.md)
und der [If-Match-Vertrag](optimistic-locking.md) sind davon unabhängige
Fehlerbehandlungs- und Integritätsverträge.

# Begründung und Konsequenzen

Ein gemeinsamer Endpoint lässt sich mit den vorhandenen Compose-Healthchecks
verwenden. Er koppelt Gesamtbereitschaft bewusst an Dienste, die nicht jede
einzelne Anfrage benötigt. Queue-Rückstand oder Sicherungsalter verlangen
separate Betreiberalarme statt den Dienst allein wegen dieser Messwerte aus
der Readiness zu nehmen.

# Citations

[1] `backend/src/katalon/main.py` — `health`
[2] `backend/src/katalon/workers/health_tasks.py`
[3] `backend/tests/test_health.py`
[4] `docs/02_produktion.md` — Monitoring
