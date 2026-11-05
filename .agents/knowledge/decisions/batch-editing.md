---
type: Decision
title: Massenbearbeitung (Batch Editing) für Records
description: Admin-UI erlaubt seitenübergreifende Auswahl von Records und Massenoperationen (Status, Feld setzen/anhängen/leeren, Relationen) mit Audit-Log-Transparenz, ohne automatischen Rollback oder Snapshots.
tags: [batch-editing, admin, frontend, backend, audit, concurrency]
timestamp: 2026-08-26T14:30:00Z
---

# Kontext

Redaktionelle Arbeit in GLAM-Sammlungen ändert oft viele Datensätze gleichzeitig: Status setzen nach Qualitätsprüfung, Felder korrigern, Verknüpfungen zu einer Person ergänzen. Bisher musste jeder Record einzeln geöffnet werden. GitHub-Issue [#138](https://github.com/karkraeg/Katalon/issues/138) fordert eine Massenbearbeitung in der Admin-UI.

# Entscheidung

**1. Unterstützte Operationen.** Der Batch-Endpoint akzeptiert eine einzelne Operation pro Request:

| Operation | Backend-Key | Frontend-Name |
|---|---|---|
| Status setzen | `set_status` | Status setzen |
| Feld überschreiben | `set_field` | Feld setzen |
| Wert anhängen (repeatable) | `append_field` | Feld anhängen |
| Feld leeren | `clear_field` | Feld leeren |
| Relation hinzufügen | `add_relation` | Relation hinzufügen |
| Relation entfernen | `remove_relation` | Relation entfernen |

**2. Auswahl: explizite IDs oder alle Treffer der aktuellen Suche.** Die Admin-UI sendet entweder `ids` oder `filters`. `filters` verwendet dieselben Parameter wie die Listen-Endpoint (`status`, `q`, Subtyp-Schlüssel, bei Vorgängen `due_before`/`reference_number`). Damit ist „alle 247 Records dieser Suche“ seitenübergreifend möglich.

**3. Async-Pfad ab 100 Records.** Kleine Batches laufen synchron im Request; ab 100 Ziel-Records wird der Job an Celery übergeben und ein `task_id` zurückgegeben. Das Frontend zeigt die Task-ID an; Polling des Status ist vorerst nicht implementiert.

**4. Kein automatischer Rollback, keine automatischen Snapshots.** Stattdessen eine klare Warnung ab 50 ausgewählten Records im Frontend. Jede Änderung wird pro Record ins `audit_log` geschrieben mit `batch_job_id`, `action: batch_update` bzw. `relation_add`/`relation_delete`. Snapshots müssen vorher manuell angelegt werden, wenn ein Rollback gebraucht wird.

**5. Per-Record-Nested-Transaction.** Innerhalb eines Batches wird jeder Record in einer eigenen nested transaction verarbeitet. Validierungsfehler oder Konflikte für einzelne Records rollen nur diesen Record zurück, nicht die Geschwister.

**6. Reindex und Relations-Sync.** Nach jeder erfolgreichen Record-Änderung wird `index_record` aufgerufen und `sync_schema_relations` läuft für betroffene Metadatenfelder.

# Begründung

- **Nur eine Operation pro Request** reduziert UI-Komplexität und Fehlerquellen; mehrere Operationen können vom Client sequentiell abgesetzt werden.
- **Seitenübergreifende Filter-Auswahl** vermeidet, dass Kurator:innen Seiten manuell durchklicken müssen, und nutzt die bestehende Listen-Suche.
- **Audit-Log statt Rollback** ist für den MVP ausreichend: Änderungen sind nachvollziehbar, und Snapshots können bei Bedarf manuell vorher erstellt werden. Automatischer Rollback wäre deutlich aufwendiger (umgekehrte Operationen, Feld-Wiederherstellung).
- **Nested transactions** verhindern, dass ein fehlerhafter Datensatz den ganzen Batch blockiert; die API returned `affected` plus `errors` pro Record.

# Scope-Grenzen

- Keine Undo-Funktion.
- Kein automatisches Polling für async Batches im Frontend.
- Felder vom Typ `group`, `pid` und `authority` können nicht per Batch bearbeitet werden.
- Vokabularfelder erlauben im MVP entweder ein ausgewähltes Vokabular-Term oder (bei `vocab_free`) einen Freitext.

# Citations

- `backend/src/katalon/api/v1/batch.py` — Router `POST /v1/batch/{record_type}`
- `backend/src/katalon/services/batch_service.py` — `resolve_record_ids`, `apply_batch`, Per-Record-Transaktionen
- `backend/src/katalon/workers/batch_tasks.py` — Celery-Task `batch_edit_task`
- `backend/src/katalon/core/schemas.py` — `BatchRequest`, `BatchOperation`, `BatchResponse`
- `backend/tests/integration/test_batch_editing.py` — 8 Integrationstests
- `frontend/admin/src/components/screens/BatchEditModal.tsx` — Modal-UI
- `frontend/admin/src/components/screens/ScreenList.tsx` — Auswahl und Action Bar
- `frontend/admin/src/api/client.ts` — `batch` Methoden pro Record-Typ
