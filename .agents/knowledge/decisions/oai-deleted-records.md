---
type: Decision
title: OAI-PMH-Löschmeldungen über oai_record_states (deletedRecord transient)
description: Depublizierte und gelöschte Datensätze werden per OAI-PMH als deleted gemeldet; eine schmale Tabelle merkt sich, welche Datensätze je öffentlich waren, gepflegt im zentralen Indexpfad.
tags: [oai-pmh, export, ddb, backend]
timestamp: 2026-10-16T14:00:00Z
---

# Kontext

Mit `deletedRecord=no` bemerkten inkrementelle Harvester Rücknahmen nie: Ein
depublizierter Datensatz bleibt im Index als `internal` (OAI filtert ihn weg), ein
gelöschter verschwindet ganz. Mit Rechteprüfungen (z. B. Lizenzpflicht) fallen zusätzlich Datensätze aus der
Auslieferung, sobald z. B. eine Bildlizenz fehlt.

# Entscheidung

- Tabelle `oai_record_states(record_type, record_id, deleted_at)`: eine Zeile je Datensatz,
  der öffentlich war. `search_service.index_record()`/`remove_record()` pflegen sie über
  `oai_state_service` in derselben Transaktion wie die Datensatzänderung.
- Nie öffentliche Datensätze bekommen keine Zeile, damit interne IDs nicht über OAI sichtbar werden.
- OAI pagt erst die Live-Datensätze (ES, search_after), dann die Löschungen (DB, Keyset
  über `(deleted_at, record_id)`); der Token trägt die Phase.
- Datensätze, die im Format nicht auslieferbar sind (Pflichtfelder, Rechteprüfungen), bekommen einen
  deleted-Header statt zu fehlen.
- Policy `transient`: Rücknahmen vor der Migration (Seed aller aktuell öffentlichen Datensätze)
  sind unbekannt.

# Begründung

Abgelehnt: Tombstones im Elasticsearch-Index. Shadow-Index, Bulk-Reindex mit Stale-Löschung
und Index-Swap hätten sie verloren oder als „stale“ entfernt. Die DB-Tabelle ist klein,
transaktional mit der Statusänderung und unabhängig vom Indexzustand. Abgelehnt außerdem:
Löschmeldungen aus `deleted_at`/`status` der Datensatztabellen direkt ableiten. Das hätte
die IDs nie veröffentlichter Entwürfe preisgegeben.

# Portal, SEO und ARK

Die Tabelle dient auch als Merkmal „war einmal öffentlich“: Portal-Detailrouten, SEO-HTML und
ARK-Resolver antworten für solche Datensätze mit `410` („zurückgezogen“), auch nach einer
Umstellung auf intern oder Entwurf. Das `410` trägt `Cache-Control: no-store`, weil Browser es
sonst unbegrenzt cachen und ein wiederhergestellter Datensatz unsichtbar bliebe. Abgelehnt:
eine eigene Spalte je Datensatztabelle (zweite Quelle für dieselbe Information).

# Citations

[1] backend/src/katalon/services/oai_state_service.py
[2] backend/src/katalon/api/v1/oai.py
[3] backend/migrations/versions/0083_oai_record_states.py
