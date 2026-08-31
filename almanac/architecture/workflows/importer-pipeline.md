---
title: "Importer Pipeline"
summary: "Katalon's importer pipeline moves CSV, Excel, and XML files through upload, mapping, dry-run validation, optional media-reference capture, vocabulary reconciliation, and Celery-backed record creation."
topics: [architecture, workflows, importer, celery, metadata, media, vocabularies]
sources:
  - id: importer-api
    type: file
    path: backend/src/katalon/api/v1/importer.py
  - id: importer-service
    type: file
    path: backend/src/katalon/services/importer_service.py
  - id: format-registry
    type: file
    path: backend/src/katalon/services/importer/formats/registry.py
  - id: csv-format
    type: file
    path: backend/src/katalon/services/importer/formats/csv_format.py
  - id: excel-format
    type: file
    path: backend/src/katalon/services/importer/formats/excel_format.py
  - id: xml-format
    type: file
    path: backend/src/katalon/services/importer/formats/xml_format.py
  - id: importer-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenImporter.tsx
  - id: upload-step
    type: file
    path: frontend/admin/src/components/screens/importer/StepUpload.tsx
  - id: importer-state
    type: file
    path: frontend/admin/src/components/screens/importer/useImporterState.ts
  - id: admin-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: media-step
    type: file
    path: frontend/admin/src/components/screens/importer/StepMedia.tsx
  - id: import-task
    type: file
    path: backend/src/katalon/workers/import_tasks.py
  - id: email-task
    type: file
    path: backend/src/katalon/workers/email_tasks.py
  - id: media-reference-service
    type: file
    path: backend/src/katalon/services/media_batch_import_service.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
---

Katalon's importer pipeline is an admin workflow for turning tabular or XML source data into Objects, Entities, Places, and Occurrences. The frontend guides users through upload, optional XML record selection, mapping, dry-run review, and background import; the backend stores parsed rows temporarily in Redis, validates mappings against field definitions, and queues a Celery task for persistent writes [@importer-screen] [@importer-api]. The task applies transforms, creates missing vocabulary terms, handles ID number and upsert strategies, logs creation, indexes imported records, and triggers a bulk reindex after successful changes [@import-task].

## Format Detection And Upload

The backend accepts CSV, TSV, Excel `.xlsx`, and XML uploads with an aggregate limit of 100 MB per upload request, including the sum of multiple XML files [@importer-api]. Format detection goes through a registry ordered as Excel, CSV, then XML, so Excel magic bytes are checked before filename-only CSV/TSV matching [@format-registry]. CSV and TSV files are decoded with UTF-8 BOM handling and use `csv.Sniffer` to detect common delimiters [@csv-format]. Excel files are read with `openpyxl` from the active worksheet, using the first row as headers [@excel-format].

XML has a separate first step because users must choose which element represents one record. The upload endpoint stores raw XML in Redis, returns element levels from `XmlFormat.list_element_levels()`, and later `/xml-selectors` converts the selected Clark-notation tag into selectors, parsed rows, preview rows, and type suggestions [@importer-api] [@xml-format]. Parsed row uploads expire after one hour because Redis keys are stored with `_UPLOAD_TTL = 3600` [@importer-api].

## Frontend State Machine

`ScreenImporter` has separate metadata and media tabs; the metadata tab drives record imports, while the media tab belongs to the media batch workflow [@importer-screen]. CSV and Excel use four steps: upload, mapping, dry-run, and import result. XML uses five steps by inserting an element-selection step before mapping [@importer-screen].

`useImporterState()` owns the reducer state and the API calls. It persists mapping choices, the optional media selector, and import options in `localStorage`, but deliberately does not persist uploaded rows, so restored sessions require re-upload when the upload ID is gone [@importer-state]. The hook also loads field definitions and subtypes for the chosen record type, auto-maps obvious column names, and polls Celery task status every 1.5 seconds while an import task is active [@importer-state].

The import API records each queued task ID in Redis for 24 hours. This distinguishes a queued Celery task from Celery's otherwise ambiguous `PENDING` state for an unknown or expired task, allowing the admin shell to remove stale import-status banners [@importer-api].

The metadata upload surface uses one hidden `multiple` file input for CSV, TSV, Excel, and XML, and the admin API client appends each selected file as a repeated `file` part before calling `/v1/importer/upload` [@upload-step] [@admin-client]. Folder picking through `webkitdirectory` belongs to the media batch tab, not to metadata record imports, so multi-file XML imports should use the normal file chooser's multi-select path [@media-step] [@upload-step].

## Mapping, Transforms, And Dry Run

Mappings use selectors as keys. For CSV and Excel the selector is a column header; for XML it is a Clark-notation tag path from the selected record element [@importer-api] [@xml-format]. Each mapping entry can target a metadata field or `__idno__`, and can include transform steps such as split, replace, regex extraction, trim, vocabulary mapping, and sandboxed Jinja expression rendering [@importer-api] [@importer-service].

`dry_run()` applies mappings to parsed rows, checks missing required fields, empty values, ID number mapping, type mismatches, full schema validation, and vocabulary statistics [@importer-api] [@importer-service]. For vocabulary fields, it reports how many incoming terms already exist and clusters near-duplicates with normalized Levenshtein similarity, giving the UI material for reconciliation before import [@importer-service] [@importer-api]. This is the runtime implementation behind [Fuzzy Vocabulary Clustering](../../decisions/importer/fuzzy-vocabulary-clustering).

Object imports may also carry one `media_selector`. This selector is separate from the metadata mapping and identifies a source column or XML element containing filenames. The UI can suggest a likely selector, but the user must select it explicitly. The backend rejects media selectors for non-object record types, missing selectors, and normalized filenames assigned to more than one source row [@importer-api] [@media-reference-service]. The dry-run result reports the number of rows with filenames, the total filenames, empty rows, and conflicts without writing references [@importer-api].

## Background Import

The import endpoint serializes the mapping and queues `import_records_task` with record type, rows, ID number strategy, upsert strategy, auto-publish flag, user ID, subtype, fields to create, and the optional media selector [@importer-api]. The Celery task supports only the four primary inventory record types, validates subtype existence, optionally creates requested field definitions, and loads field definitions before applying the same mapping logic used in dry-run [@import-task].

During import, vocabulary field strings are resolved case-insensitively against configured vocabularies and missing terms are created when the vocabulary exists [@import-task]. The task can generate ID numbers from configured schemas, skip, merge, or replace existing records by ID number, publish records when requested, write audit-log creation entries, and index changed records [@import-task]. After any create or update, it queues a bulk reindex for that record type so indexed documents converge with imported database state [@import-task].

When a media selector is present, the task stores one `MediaImportReference` per normalized filename and object. References are written for new objects and for existing objects reached through `skip`, `merge`, or `replace`. In the `skip` path, metadata remains unchanged while missing media references are added. The unique object-and-filename constraint and conflict-safe inserts make repeated imports idempotent. The task result reports the number of newly inserted references in `media_references_created` [@import-task] [@models].

Cancellation is cooperative. The API writes a Redis `cancel:<task_id>` key for one hour, and the task checks that key every ten rows before breaking with a warning [@importer-api] [@import-task].

After a terminal import result, the worker queues a concise result email to the triggering active staff user. The worker resolves the recipient from the stored user ID, so no address is included in the import task payload; failed notification enqueueing does not change the import result [@import-task] [@email-task].
