---
title: "Batch Editing"
summary: "Admin workflow for applying one operation (status, field, or relation) to many records at once, either by explicit IDs or by all current list-filter results."
topics: [workflows, admin, records, audit, backend, frontend]
sources:
  - id: decision
    type: file
    path: .agents/knowledge/decisions/batch-editing.md
  - id: backend-router
    type: file
    path: backend/src/katalon/api/v1/batch.py
  - id: backend-service
    type: file
    path: backend/src/katalon/services/batch_service.py
  - id: backend-worker
    type: file
    path: backend/src/katalon/workers/batch_tasks.py
  - id: backend-schemas
    type: file
    path: backend/src/katalon/core/schemas.py
  - id: frontend-modal
    type: file
    path: frontend/admin/src/components/screens/BatchEditModal.tsx
  - id: frontend-list
    type: file
    path: frontend/admin/src/components/screens/ScreenList.tsx
  - id: frontend-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: docs
    type: file
    path: docs/05_batch_bearbeitung.md
---

# Batch Editing

The Admin UI lets curators select many records and apply a single operation to all of them. Selection can be explicit (checkboxes on the current page) or implicit ("all records matching the current search/filter across pages"). The backend handles small batches synchronously and large batches (>100 records) asynchronously via Celery.

## When to Use

Use this workflow when the same change must be applied to many records without opening each record individually. Typical GLAM examples:

- Set 50 object records to `public` after a quality review.
- Append a language term to a repeatable field on a group of records.
- Link a batch of objects to the same photographer entity.
- Clear a deprecated field across all records of one subtype.

## Selecting Records

In any record list screen the leftmost checkbox selects a single record. The header checkbox selects all records on the current page. When at least one record on the page is selected and the total result set is larger than one page, the bulk bar offers **"Alle N Datensätze dieser Suche auswählen"** to switch to filter-based selection. The filter set is captured from the current list view: status tab, search query, subtype filter, and procedure-specific filters (`due_before`, `reference_number`).

## Supported Operations

The modal supports one operation per request:

| Operation | What it does |
|---|---|
| Status setzen | Changes `status` for all selected records. Allowed values depend on the record family. |
| Feld setzen | Overwrites a single metadata field. For repeatable text fields the UI accepts a list of values. |
| Feld anhängen | Appends one value to a repeatable field. Errors if the field is not repeatable. |
| Feld leeren | Resets the field to its empty default (empty string, `[]`, `false`, or `null`). |
| Relation hinzufügen | Creates a relation from every selected record to one target record. |
| Relation entfernen | Deletes a matching relation from every selected record to one target record. |

Group fields, PID fields, and authority fields are excluded from the field dropdown because their semantics are not safe to edit blindly.

## Warning and Safety

A warning is shown when more than 50 records are selected. The user must confirm before the operation runs. There is **no automatic rollback** and **no automatic snapshot** before a batch operation. Every successful change is written to the audit log with `batch_job_id` so an administrator can trace what changed. Manual snapshots can be created before a batch operation if a restore point is needed.

## Async Path

If the resolved record count exceeds 100, the endpoint returns a `task_id` and hands the work to Celery. The modal shows the task ID; polling is not implemented yet, so users refresh the list to see results.

## Backend Flow

1. `POST /v1/batch/{record_type}` receives `operation` plus either `ids` or `filters`.
2. `resolve_record_ids` turns `filters` into a UUID list using the same filters as the list endpoint.
3. For each record, `apply_batch` runs a nested transaction:
   - Load the record.
   - Apply status, field, or relation operation.
   - Validate metadata.
   - Sync schema-derived relations.
   - Write an audit-log entry with `batch_job_id`.
   - Reindex the record in Elasticsearch.
4. Errors for individual records are collected; siblings are not rolled back.

## Code Entry Points

- Backend router: `backend/src/katalon/api/v1/batch.py`
- Backend service: `backend/src/katalon/services/batch_service.py`
- Celery task: `backend/src/katalon/workers/batch_tasks.py`
- Pydantic models: `backend/src/katalon/core/schemas.py` (`BatchRequest`, `BatchOperation`, `BatchResponse`)
- Frontend modal: `frontend/admin/src/components/screens/BatchEditModal.tsx`
- Frontend list/selection: `frontend/admin/src/components/screens/ScreenList.tsx`
- API client wrappers: `frontend/admin/src/api/client.ts` (`objects.batch`, `entities.batch`, etc.)
