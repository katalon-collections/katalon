---
type: Decision
title: Optimistic Locking mit feldweisem 3-Wege-Merge bei Bearbeitungskonflikt
description: version-Spalte + If-Match-Header + 409 verhindert stilles Überschreiben bei parallelem Edit; bei Konflikt macht die Admin-UI einen 3-Wege-Merge (base/server/mine) und fragt nur bei echten Feld-Kollisionen nach.
tags: [concurrency, datenintegrität, backend, frontend, ux]
timestamp: 2026-07-13T06:40:00Z
---

# Kontext

Aus dem Production-Readiness-Audit (#272): Zwei Kurator:innen editieren
denselben Record gleichzeitig → last-write-wins. PUT ersetzt den ganzen Record
(inkl. `metadata_`), also überschreibt der zweite Speichervorgang jede Änderung
des ersten — still, ohne Fehler oder Log. Für ein MMS mit mehreren gleichzeitig
arbeitenden Kurator:innen ist das der wahrscheinlichste reale Integritätsverlust
(nicht Scale). Siehe [[production-readiness-posture]], wo dieser Bedarf bewusst
als Issue vertagt wurde.

# Entscheidung

**1. `version INT` als Concurrency-Token, nicht `updated_at`.** Alle sieben
Record-Tabellen besitzen eine monoton steigende `version`-Spalte. Migration 0027
führte sie für die damaligen fünf Typen ein; Collection und StorageLocation
folgen demselben Vertrag. Der
Endpoint erhöht sie bei jedem Update. `updated_at` als ETag wurde verworfen:
Datetime-Round-Trip (Mikrosekunden, TZ, Serialisierung) ist fragil; ein Integer
ist eindeutig. Kosten: eine Migration.

**2. `If-Match` ist für REST-Updates, Publish und Snapshot-Restore Pflicht.**
`require_version()` liefert bei fehlendem Header `428`; ein veralteter Wert
führt zu `409 {"error":"version_conflict","current_version":N}`.
Die frühe Entscheidung für einen optionalen Header ist abgelöst. Direkte
Service-Schreibpfade von Importer und Batch sind keine REST-Ausnahme: sie rufen
diese HTTP-Endpunkte nicht auf. `check_version()` bleibt die gemeinsame
Vergleichsfunktion unter `require_version()`. ORM-Versionierung und
`flush_record()` behandeln zusätzlich konkurrierende Datenbank-Schreibzugriffe.

**3. Bei Konflikt: feldweiser 3-Wege-Merge in der Admin-UI, kein blindes
Reload/Overwrite.** Ein vollständiges Neuladen würde B's ungespeicherte Arbeit verwerfen;
ein Überschreiben könnte A's Änderungen verlieren. Die UI holt auf
409 den Serverstand und vergleicht pro Metadatenfeld drei Stände:

| base (geladen) | server (A) | mine (B) | Aktion |
|----------------|-----------|----------|--------|
| =base | geändert | =base | automatisch A |
| =base | =base | geändert | automatisch B |
| — | geändert | geändert, ≠ server | **Dialog: B wählt A oder mein** |

Nur echte beidseitige Kollisionen landen im Dialog; alles andere wird
automatisch gemergt. Danach PUT mit der neuen Server-Version. B's Edits liegen
bis dahin unangetastet im React-State — die 409 zerstört nie Arbeit.

# Begründung / Scope-Grenzen

- **Optimistic statt pessimistic Locking**: kein serverseitiger Lock-State,
  keine Lock-Leichen bei Tab-Close. Standard für Web-CRUD.
- **Feldebene, nicht Elementebene**: bei wiederholbaren Feldern zählt der ganze
  Array-Wert als Einheit. Element-Level-Merge wäre deutlich mehr UI für einen
  seltenen Fall.
- **Nur Metadatenfelder werden gemergt/abgefragt.** Skalare (idno, status,
  subtype, collection_status, Daten) werden aus B's Payload übernommen
  (mine-wins). Diese Skalare besitzen keine eigene interaktive Merge-Auflösung.
  Eine reine Skalar-Änderung von A während des Konfliktfensters kann dadurch
  verloren gehen. Diese Grenze gilt unabhängig davon, wie häufig solche
  Paralleländerungen auftreten.
- **Kein automatischer 3-Wege-Textmerge** (wie Git). Bei Kollision entscheidet
  der Mensch pro Feld; eine zusätzliche Textmerge-Logik wird nicht eingeführt.

# Citations

- `backend/src/katalon/core/concurrency.py` — `require_version`, `check_version`, `flush_record`
- `backend/migrations/versions/0027_record_version.py`
- `backend/src/katalon/api/v1/{objects,entities,places,occurrences,procedures,collections,storage_locations}.py` — `If-Match`-Guard
- `frontend/admin/src/api/client.ts` — `VersionConflictError`, `ifMatch`
- `frontend/admin/src/components/screens/ScreenForm.tsx` — `resolveConflict`, `commitMerge`, `ConflictDialog`
- `backend/tests/test_optimistic_locking.py`
