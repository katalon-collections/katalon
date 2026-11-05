---
title: "Working Sets (Arbeitslisten)"
summary: "Admin workflow for ad-hoc, type-bound groupings of records for internal tasks such as exhibition checklists, curatorial reviews, and batch editing."
topics: [workflows, working-sets, admin, records, batch, backend, frontend]
sources:
  - id: backend-router
    type: file
    path: backend/src/katalon/api/v1/working_sets.py
  - id: backend-service
    type: file
    path: backend/src/katalon/services/working_set_service.py
  - id: backend-models
    type: file
    path: backend/src/katalon/core/models.py
  - id: backend-schemas
    type: file
    path: backend/src/katalon/core/schemas.py
  - id: frontend-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenWorkingSets.tsx
  - id: frontend-modal
    type: file
    path: frontend/admin/src/components/screens/AddToWorkingSetModal.tsx
  - id: frontend-list
    type: file
    path: frontend/admin/src/components/screens/ScreenList.tsx
---

# Working Sets (Arbeitslisten)

Working Sets (Arbeitslisten) provide curators and staff with ordered, ad-hoc groupings of records of a specific record type for internal projects, quality checks, exhibition preparation, and [batch operations](batch-editing) [@backend-models] [@backend-router].

Unlike permanent archival holdings (`collection`) or exhibitions (`occurrence`), Working Sets are lightweight, relational groupings without schema-engine fields or public visibility [@backend-models].

## Characteristics

- **Type-bound:** Each Working Set is bound to exactly one record type (`object`, `entity`, `place`, `occurrence`, `procedure`, `collection`, `storage_location`) [@backend-schemas].
- **Internal only:** Working Sets are never published to the public portal and carry no public PIDs or OAI-PMH sets [@backend-models].
- **Ordered:** Records within a set maintain an explicit `sort_order` that can be adjusted [@backend-models] [@backend-router].
- **Contextual annotations:** Each item in a set can store an optional free-text `note` (e.g. exhibition display case, conservation status, duplicate verification note) [@backend-schemas].
- **Sharing model:** Sets are either private (`is_shared = false`, visible to creator and administrators) or shared (`is_shared = true`, visible and editable by all staff) [@backend-service].

## Workflow Integration

1. **Selection to Worklist:**
   In any record list screen (`ScreenList`), selecting records exposes the button **"Zu Arbeitsliste"** in the bulk action bar. Curators can add the selected records to an existing worklist of that type or create a new worklist on the fly.
   [@frontend-list] [@frontend-modal]
2. **Worklist Management (`ScreenWorkingSets`):**
   Staff navigate to **Arbeitslisten** via the main navigation. The overview lists "Meine Arbeitslisten" and "Geteilte Arbeitslisten" with item counts, search, and type filters.
   [@frontend-screen]
3. **Detail and Ordering:**
   Opening a worklist shows a table of all included records with thumbnails, title labels, ID numbers, status badges, editable inline notes, and reordering controls.
   [@frontend-screen] [@backend-service]
4. **Bridge to Batch Editing:**
   The **"Batch-Bearbeitung"** action in the worklist detail view directly opens [Batch Editing](batch-editing) with `BatchEditModal` loaded with the record IDs of the working set, enabling status updates, field changes, or relation additions across all set records in one step.
   [@frontend-screen]
