---
type: Decision
title: Production-Readiness — ein tiefer /health-Endpoint, Optimistic Locking bewusst vertagt
description: /health prüft DB und Elasticsearch aktiv statt statisch OK zu liefern (kein Split Liveness/Readiness); Optimistic Locking gegen paralleles Überschreiben ist ein realer Bedarf, aber bewusst als Issue vertagt statt sofort gebaut.
tags: [ops, health, concurrency, betrieb, audit]
timestamp: 2026-07-13T05:14:00Z
---

# Kontext

Production-Readiness-Audit 2026-07-13, ausgelöst durch die Frage, ob der
verbreitete "Prototyp ≠ Produktion"-Einwand für Katalon zutrifft. Ergebnis:
Der Skalierungs-Teil (50k Websockets, Replikation, Presence) ist für ein
GLAM-MMS mit einer Institution und wenigen gleichzeitigen Kurator:innen
irrelevant. Relevant sind Datenintegrität, Ops und Edge Cases. Zwei Punkte
brauchten eine Design-Entscheidung.

# Entscheidung

**1. Ein tiefer `/health`-Endpoint statt statischem OK oder Split
Liveness/Readiness.** `/health` pingt Postgres (`SELECT 1`) und
Elasticsearch und liefert `503` mit `{"status": "degraded", "checks": {...}}`,
wenn eine Abhängigkeit fehlt (vorher statisch `{"status": "ok"}`). Kein
getrennter Liveness-/Readiness-Split (wie in Kubernetes üblich), weil das
Deployment Docker Compose ist, nicht k8s — der Compose-Healthcheck und das
`depends_on: condition: service_healthy` reichen. Redis wird bewusst **nicht**
im Endpoint geprüft: Celery-Broker-Ausfall darf die API nicht als "unhealthy"
markieren, solange lesende/schreibende Requests weiter funktionieren.

**2. Optimistic Locking wird vertagt, nicht sofort gebaut.** Paralleles
Editieren desselben Records ist aktuell last-write-wins (stilles
Überschreiben). Das ist der wahrscheinlichste reale Datenintegritäts-Fehler
im Mehr-Kurator:innen-Betrieb — aber die Lösung (Version-Spalte + `If-Match`
+ 409 + Frontend-Konfliktbehandlung über alle 5 Typen) ist ein
Mittelaufwand-Feature und kein Quick Fix. Deshalb als Issue #272 erfasst
statt im Audit-Zug mitgebaut.

# Begründung

Der statische Health-Check verbarg Backend-Ausfälle vor Load Balancern —
ein Ein-Zeilen-Symptom mit realer Ops-Wirkung, also sofort gefixt. Locking
dagegen ist echtes Produkt-Scope (Migration + Endpoint + UI) und gehört in
einen eigenen, testbaren Change — die Trennung hält den Audit-Commit klein
und reviewbar. Kein Redis im Health-Check, weil Liveness der API-Schreib-/
Lesepfade nicht am Task-Queue-Zustand hängen soll.

# Status

`/health`-Fix umgesetzt und released (v0.5.9, Commit 818c0a6). Offene
Folge-Issues aus dem Audit:

- #272 Optimistic Locking (High)
- #273 Backup-Automatisierung + Restore-Drill (High)

Nicht umgesetzt (bewusst): Magic-Byte-Sniffing für Uploads — Client-MIME
ist spoofbar, aber Cantaloupe reprozessiert Bilder, Restrisiko niedrig, neue
Dependency (`python-magic`) nicht gerechtfertigt (YAGNI).

# Citations

[1] Commit 818c0a6 "feat(health): /health verifies DB and Elasticsearch"
[2] `backend/src/katalon/main.py` — `health()`-Handler
[3] GitHub Issues #272, #273
[4] Production-Readiness-Audit 2026-07-13
