---
type: Playbook
title: DB-Problem-Eskalation
description: Bei Datenbankfehlern nie Volumes löschen — erst Logs lesen, dann Karl informieren, erst nach Freigabe handeln.
tags: [datenbank, sicherheit, eskalation]
timestamp: 2026-07-09T00:00:00Z
---

# Trigger

Passwort-Konflikte, Schema-Probleme, Container-Fehler rund um Postgres.

# Absolutes Verbot

Niemals `docker compose down -v` oder Datenbank-Volumes löschen/neu erstellen ohne
explizite Bestätigung von Karl — auch nicht, wenn es als schnelle Lösung erscheint.
Datenverlust ist irreversibel.

# Schritte

1. Logs lesen, Root Cause verstehen (nie Annahmen treffen).
2. Karl informieren und Optionen vorlegen.
3. Erst nach ausdrücklicher Freigabe handeln.

# Citations

[1] Root `AGENTS.md`, Abschnitt "Datensicherheit – ABSOLUTE VERBOTE"
