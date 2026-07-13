---
type: Decision
title: Broker-toleranter Celery-Enqueue — Fire-and-forget schluckt, Job-ID-Pfade liefern 503
description: Fire-and-forget-.delay()-Aufrufe im Request-Pfad dürfen bei Redis-Broker-Ausfall den bereits erfolgreichen Schreibvorgang nicht in ein 500 verwandeln; ein Helper schluckt+loggt, während Endpunkte mit Job-ID ein sauberes 503 liefern.
tags: [concurrency, ops, celery, resilience, backend]
timestamp: 2026-07-13T10:20:00Z
---

# Kontext

Beim Fix eines Integrationstests (v0.6.1) fiel auf: `cleanup_relation_refs.delay()`
im DELETE-Handler erwartete einen Redis-Broker. Ohne Redis wirft `.delay()`
`ConnectionRefusedError`, und weil der Aufruf ungeschützt im Request-Pfad steht,
endet ein DELETE mit **500** — obwohl der eigentliche DB-Schreibvorgang bereits
committed war. Dasselbe Muster fand sich an ~12 Stellen (Relation-Cleanup aller
5 Typen, IIIF-Tile-Generierung beim Upload, Reindex, Reconciliation, Batch-/
Record-Import).

Das widerspricht direkt der bereits festgelegten Haltung aus
[[production-readiness-posture]]: `/health` prüft Redis bewusst **nicht**, weil
ein Celery-Broker-Ausfall lesende/schreibende Pfade nicht als "unhealthy"
markieren soll. Wenn aber jedes DELETE bei Broker-Ausfall 500t, war dieser
Anspruch im Code nicht eingelöst.

# Entscheidung

Zwei Enqueue-Helper in `workers/enqueue.py`, je nach Semantik des Aufrufs:

**1. `enqueue(task, *args, **kwargs)` — Fire-and-forget, schluckt Broker-Fehler.**
Für Hintergrundarbeit, die *Nebeneffekt* eines anderen primären Vorgangs ist und
deren Ausbleiben den Request nicht ungültig macht: Relation-Cleanup nach Delete,
IIIF-Tiles nach Upload, Reindex nach Schema-Änderung. Broker-Fehler wird geloggt
(`logger.warning(..., exc_info=True)`), der Request läuft normal weiter.

**2. `enqueue_or_503(task, ...)` — liefert `503` bei Broker-Ausfall.**
Für Endpunkte, bei denen der Job der *Zweck* des Requests ist: solche, die eine
Job-ID zum Pollen zurückgeben (Batch-Media-Import, Record-Import), und explizit
nutzer-getriggerte Reindex-/Reconciliation-Endpunkte. Ein „queued" zu melden,
wenn nichts eingereiht wurde, wäre eine Lüge — also ehrliches `503`.

# Begründung

- **Nebeneffekt ≠ Zweck.** Die Unterscheidung ist die eigentliche
  Design-Entscheidung: Nicht pauschal schlucken (verschluckt echte Fehler bei
  Import/Reindex, wo der Nutzer ein Ergebnis erwartet) und nicht pauschal 503en
  (bricht Delete/Upload, deren Kern-Wirkung schon passiert ist).
- **Kein stilles `except: pass`.** Der Helper loggt immer. Ein bereits
  existierendes `except: pass` in `schema_admin.py` wurde dabei ersetzt.
- **Alternativen verworfen:** (a) Broker-Health in `/health` aufnehmen und API
  bei Redis-Ausfall komplett als down melden — widerspricht der Posture, bestraft
  funktionierende Lese-/Schreibpfade. (b) Jeden Aufruf einzeln in `try/except`
  wickeln — dupliziert Logging-Logik ~12-fach; ein Helper ist DRY und macht die
  Semantik (schlucken vs. 503) an der Aufrufstelle lesbar.

# Citations

- `backend/src/katalon/workers/enqueue.py` — `enqueue`, `enqueue_or_503`
- `backend/src/katalon/api/v1/{objects,entities,places,occurrences,procedures}.py` — Delete-Cleanup
- `backend/src/katalon/api/v1/{media,search,schema_admin,index_health,importer}.py` — Tiles/Reindex/Import
- `backend/tests/test_enqueue.py`
- GitHub Issue #274
