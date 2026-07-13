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

**1. `version INT` als Concurrency-Token, nicht `updated_at`.** Jede der fünf
Record-Tabellen (objects/entities/places/occurrences/procedures) bekommt eine
monoton steigende `version`-Spalte (Migration 0027, `server_default="1"`). Der
Endpoint erhöht sie bei jedem Update. `updated_at` als ETag wurde verworfen:
Datetime-Round-Trip (Mikrosekunden, TZ, Serialisierung) ist fragil; ein Integer
ist eindeutig. Kosten: eine Migration.

**2. `If-Match`-Header, nur bei Anwesenheit erzwungen.** Der Client sendet
`If-Match: <version>`. Bei Mismatch → `409 {"error":"version_conflict",
"current_version":N}` (Helper `core/concurrency.py::check_version`, geteilt über
alle fünf Endpoints). Fehlt der Header, wird **nicht** geprüft — Importer und
Skripte behalten ihr Verhalten, die Admin-UI sendet ihn immer. Das schützt den
realen Client, ohne die API für Batch-Nutzer zu brechen.

**3. Bei Konflikt: feldweiser 3-Wege-Merge in der Admin-UI, kein blindes
Reload/Overwrite.** Ein naives "neu laden" verwirft B's Arbeit, ein blindes
"trotzdem speichern" verwirft A's — beide schlecht. Stattdessen holt die UI auf
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
  (mine-wins). Bewusste Scope-Grenze: skalare Parallel-Edits sind selten und
  meist absichtlich. Bekannte Grenze: eine reine Skalar-Änderung von A während
  des Konfliktfensters kann verloren gehen — akzeptiert für MVP.
- **Kein automatischer 3-Wege-Textmerge** (wie Git). Bei Kollision entscheidet
  der Mensch pro Feld; das ist billiger und nachvollziehbarer.

# Citations

- `backend/src/katalon/core/concurrency.py` — `check_version`
- `backend/migrations/versions/0027_record_version.py`
- `backend/src/katalon/api/v1/{objects,entities,places,occurrences,procedures}.py` — `If-Match`-Guard
- `frontend/admin/src/api/client.ts` — `VersionConflictError`, `ifMatch`
- `frontend/admin/src/components/screens/ScreenForm.tsx` — `resolveConflict`, `commitMerge`, `ConflictDialog`
- `backend/tests/test_optimistic_locking.py`
