---
type: Decision
title: Bulk-Reindex — Koordination pro Typ über Redis-Marker, Streaming statt Vorab-Löschen
description: Rebuild-Anfragen werden pro Typ zusammengefasst (queued/dirty), die Run-Sperre ist nicht-blockierend mit kurzer, verlängerter Lease, und der Rebuild überschreibt batchweise per ID statt den Typ erst zu löschen.
tags: [search, elasticsearch, celery, ops, backend]
timestamp: 2026-10-13T14:00:00Z
---

# Kontext

Auf dem BPK-Server (Bildpostkarten, ~32.000 Objekte; Worker `--pool=threads`,
`task_acks_late`) führte jede Schemaänderung zu einem eigenen `bulk_reindex_type`
(10-s-Fenster in `_claim_reindex_trigger`). Zwei Änderungsrunden ergaben 12 Jobs,
wartende Jobs blockierten Worker-Threads bis zu 1 h auf der Redis-Sperre
(`blocking_timeout=3600`), nach Ablauf der festen 1-h-Lease liefen Jobs parallel.
Der Task hielt alle Dokumente eines Typs im Speicher (5,9 GB RSS, OOM-Kills), und
das Portal hatte keinen Fortschritt außer Logzeilen.

# Entscheidung

- **Koordination über drei Redis-Keys pro Typ** (`workers/reindex_state.py`):
  `queued` (ein wartender Job existiert), `dirty` (DB-Stand seit Start des
  letzten Laufs geändert), Run-Lock. Alle Rebuild-Anfragen laufen über
  `request_bulk_reindex()`; daraus folgen höchstens ein laufender und ein
  Folgejob pro Typ. Ein Job ohne `dirty` überspringt (`coalesce=True`).
- **Nicht-blockierende Sperre mit 2-min-Lease + Watchdog-Thread** statt
  1-h-Lease/1-h-Warten. Wartende Jobs geben den Thread sofort frei
  (`deferred`); der laufende Job startet beim Ende genau einen Folgejob.
  Freigabe bei `worker_shutdown`.
- **Streaming**: ID-Snapshot, Aufbau und Versand in Batches, Überschreiben per
  ID, danach Abgleich veralteter Dokumente (mit DB-Gegenprobe gegen in der
  Zwischenzeit angelegte Datensätze). Kein `delete_by_query` vorab.
- **Fortschritt** als Redis-Hash, gelesen über `GET /v1/admin/index-status`.
- **Ergänzung (gleicher Tag):** Eine globale Run-Sperre statt einer pro Typ; Tasks
  bestätigen beim Start (`acks_late=False`, sonst liefert Redis nach 1 h erneut aus),
  Crash-Recovery über die `dirty`-Marke plus `worker_ready`. Der Komplett-Neuaufbau
  baut einen frischen Index und schaltet den Alias `ES_INDEX_NAME` atomar um
  (Schatten-Schreiben + Nachzug geänderter Datensätze). Der Typ-Reindex bleibt
  in-place: Ein frischer Index pro Typ müsste alle anderen Typen mitkopieren.

# Begründung

- Ein Rebuild liest immer den aktuellen DB-Stand; mehrere wartende Jobs für
  denselben Typ bringen nichts außer CPU-Konkurrenz.
- Keine neue Tabelle und keine Celery-Erweiterung (z. B. celery-once): Redis
  ist ohnehin Broker und Lock-Store.
- Prefork-Pool verworfen: hätte `Dockerfile.worker` und damit die
  `katalon-cli`-Compose-Topologie geändert. Der "different loop"-Fehler kam
  aus der gepoolten API-Engine in `purge_tasks.py`; NullPool-Engine pro Lauf
  behebt ihn im bestehenden Thread-Pool.
- Kein Vorab-Löschen: das Portal zeigt während eines Laufs den alten Stand
  statt einer leeren oder halb gefüllten Trefferliste.

# Citations

- `backend/src/katalon/workers/reindex_state.py`
- `backend/src/katalon/workers/index_tasks.py`
- `backend/tests/test_reindex_coordination.py`
- `backend/tests/integration/test_bulk_reindex_streaming.py`
