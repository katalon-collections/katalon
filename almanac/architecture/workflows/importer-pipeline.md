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
  - id: import-resolution
    type: file
    path: backend/src/katalon/services/import_resolution.py
  - id: import-tasks
    type: file
    path: backend/src/katalon/workers/import_tasks.py
  - id: pid-service
    type: file
    path: backend/src/katalon/services/pid_service.py
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
  - id: issue-426
    type: web
    url: https://github.com/karkraeg/Katalon/issues/426
---

Katalon's importer pipeline is an admin workflow for turning tabular or XML source data into Objects, Entities, Places, and Occurrences. The frontend guides users through upload, optional XML record selection, mapping, dry-run review, and background import; the backend stores parsed rows temporarily in Redis, validates mappings against field definitions, and queues a Celery task for persistent writes [@importer-screen] [@importer-api]. The task applies transforms, creates missing vocabulary terms, handles ID number and upsert strategies, logs creation, indexes imported records, and triggers a bulk reindex after successful changes [@import-task].

## Supported Record Types And Scope Limitations

Katalon defines seven primary record types, but the generic tabular and XML importer pipeline intentionally supports only four of them (`VALID_TYPES = {"object", "entity", "place", "occurrence"}`) [@importer-api] [@import-task]:

- **`object`** — physical and digital cultural heritage assets, artifacts, documents, and media
- **`entity`** — persons, corporate bodies, and organizations
- **`place`** — geographic places with PostGIS coordinates
- **`occurrence`** — events, exhibitions, works, and concepts

The remaining three core record types are deliberately excluded from this generic row-oriented import pipeline due to specialized domain and architectural requirements:

- **`collection`** (Archival Tectonics & Hierarchies): Collections are organized in hierarchical tree structures (`parent_id`) representing archival tectonics, series, and fonds. Safe ingestion requires top-down parent-first ordering, circular dependency prevention, and tectonic tree integrity validation that a flat row-by-row mapping pipeline cannot guarantee.
- **`procedure`** (Workflows & Processes): Procedures govern administrative museum workflows (loans, conservation, acquisitions, deaccessioning). They rely on dedicated operational state machines, deadlines, docket numbers, process statuses, and complex multi-record linkage semantics that demand workflow-specific transaction handling rather than generic tabular metadata ingestion.
- **`storage_location`** (Internal Logistics): Storage locations model physical locations in a strict internal hierarchy (building → room → row → shelf → box via `parent_id`). To preserve SPECTRUM-compliant movement history and security boundaries (theft prevention), objects link to locations via temporal generic relations (`normal_location`, `current_location`). Storage locations are strictly internal, excluded from public portals, and managed independently from generic cataloging imports.

This is the implemented scope of `VALID_TYPES`, not a promise of separate future import frameworks. Extending it requires an explicit decision about hierarchy, permissions and procedure invariants; the present exclusion alone does not establish why every future import must use a dedicated pipeline.

## Format Detection And Upload

The backend accepts CSV, TSV, Excel `.xlsx`, and XML uploads with an aggregate limit of 100 MB per upload request, including the sum of multiple XML files [@importer-api]. Format detection goes through a registry ordered as Excel, CSV, then XML, so Excel magic bytes are checked before filename-only CSV/TSV matching [@format-registry]. CSV and TSV files are decoded with UTF-8 BOM handling and use `csv.Sniffer` to detect common delimiters [@csv-format]. Excel files are read with `openpyxl` from the active worksheet, using the first row as headers [@excel-format].

XML has a separate first step because users must choose which element represents one record. The upload endpoint stores raw XML in Redis, returns element levels from `XmlFormat.list_element_levels()`, and later `/xml-selectors` converts the selected Clark-notation tag into selectors, parsed rows, preview rows, and type suggestions [@importer-api] [@xml-format]. Parsed row uploads expire after one hour because Redis keys are stored with `_UPLOAD_TTL = 3600` [@importer-api].

## Frontend State Machine

`ScreenImporter` has separate metadata and media tabs; the metadata tab drives record imports, while the media tab belongs to the media batch workflow [@importer-screen]. CSV and Excel use four steps: upload, mapping, dry-run, and import result. XML uses five steps by inserting an element-selection step before mapping [@importer-screen].

`useImporterState()` owns the reducer state and the API calls. It persists mapping choices, the optional media selector, and import options in `localStorage`, but deliberately does not persist uploaded rows, so restored sessions require re-upload when the upload ID is gone [@importer-state]. Fields to be created during import (`pendingFields`) are persisted too and appear as virtual `__pending__` options in the mapping dropdown; they are deduplicated by name and dropped from the list once a real field of that name exists, and only `__pending__` entries are labelled "(new)" [@importer-state]. The upload step offers a **New import** button that dispatches `RESET` (with a confirmation from step 2 on) to clear the persisted state [@importer-state]. The hook also loads field definitions and subtypes for the chosen record type, auto-maps obvious column names, and polls Celery task status every 1.5 seconds while an import task is active [@importer-state].

The import API records each queued task ID in Redis for 24 hours. This distinguishes a queued Celery task from Celery's otherwise ambiguous `PENDING` state for an unknown or expired task, allowing the admin shell to remove stale import-status banners [@importer-api].

`CsvFormat` decodes UTF-8 (with or without BOM) first and falls back to Windows-1252, then ISO-8859-1 (`detect_encoding`), so CSV files saved by older Excel versions keep their umlauts instead of turning into replacement characters. The upload response carries `encoding` (in effect) and `encoding_detected` for CSV/TSV; the upload form accepts `encoding` (`utf-8`, `windows-1252`, `iso-8859-1`) to override, and the mapping step offers it as a select (changing it re-uploads the file and resets the mapping, since headers change; after a page reload the file is gone and the select is disabled). Cells with U+FFFD left after decoding make the dry run warn. Excel and XML are unaffected [@csv-format] [@importer-api] [@importer-state].

The metadata upload surface uses one hidden `multiple` file input for CSV, TSV, Excel, and XML, and the admin API client appends each selected file as a repeated `file` part before calling `/v1/importer/upload` [@upload-step] [@admin-client]. Folder picking through `webkitdirectory` belongs to the media batch tab, not to metadata record imports, so multi-file XML imports should use the normal file chooser's multi-select path [@media-step] [@upload-step].

## Mapping, Transforms, And Dry Run

Mappings use selectors as keys. For CSV and Excel the selector is a column header; for XML it is a Clark-notation tag path from the selected record element [@importer-api] [@xml-format]. ID-number mapping is configured separately in the ID-number card; the ordinary target dropdown excludes the system `idno` field to prevent a second assignment. API mapping uses `__idno__` (the service also recognizes `idno` for compatibility). The mapping table shows the ID column as "→ ID-Nummer (siehe oben)" instead of "ignore", and both the dry-run and the dialog count `__idno__` as satisfying a required `idno` field [@importer-service] [@importer-state]. Each ordinary mapping entry targets a metadata field, and can include transform steps such as split, replace, regex extraction, trim, vocabulary mapping, and sandboxed Jinja expression rendering [@importer-api] [@importer-service].

`dry_run()` applies mappings to parsed rows, checks missing required fields, empty values, ID number mapping, type mismatches, full schema validation, and vocabulary statistics [@importer-api] [@importer-service]. The dry-run endpoint resolves text to vocabulary terms and relation targets with the same `services/import_resolution.py` functions as the worker. Missing terms and (with `on_missing: create`) missing relation targets are created inside a savepoint that is rolled back after validation, so the preview validates the real result and persists nothing. For vocabulary fields, it reports existing, new and (in `match_only`) dropped terms using the resolver's report and selected `vocab_modes` mode, and clusters near-duplicates with normalized Levenshtein similarity, giving the UI material for reconciliation before import [@importer-service] [@importer-api] [@import-resolution]. This is the runtime implementation behind [Fuzzy Vocabulary Clustering](../../decisions/importer/fuzzy-vocabulary-clustering).

Type coercion in `apply_mapping` converts source strings per target field type: numbers are parsed (comma-tolerant), booleans normalized, `url` fields (top-level and group sub-fields) are wrapped into their `{value, label}` object shape with an optional second source `MappingEntry.label_selector` filling `label` (paired by position when URL and label counts match; a single URL takes the first label; on differing counts the labels stay empty, because XML parsing drops empty elements. XML blocks where one URL and one label come from different elements still pair. Omitted selector yields an empty string, keeping saved templates without `label_selector` valid across dry-run and worker), and `geo` fields are parsed from `lat, lon` (comma, semicolon or whitespace separated, decimal point) into `{lat, lon}` via `_parse_geo`; unparseable or out-of-range values are dropped on import and reported as a dry-run type warning [@importer-service]. The "new field" dialog offers `text`, `number`, `date`, `boolean`, `vocab`, `relation`, `url`, `richtext`, `vocab_free` and `geo` (`FIELD_TYPE_OPTIONS`); `pid` (system-managed), `authority` (needs `{source, external_id, label}`) and `group` (needs child fields) are deliberately absent. In the mapping step the target dropdown disables a target already used by another column only when the field is not repeatable (`StepMapping.tsx`). Fields created during the import (`fields_to_create`, applied by `import_records_task`) of type `vocab` are bound to a vocabulary named after the German label (created if missing) via `ensure_field_vocabulary`; without the binding `resolve_vocab_terms` cannot resolve values and every row with a value fails validation [@import-tasks]. Several columns may map to the same target (e.g. `Genre1`..`Genre3` onto one repeatable vocabulary field): `apply_mapping` appends their values in column order instead of letting the last column win, and for repeatable top-level fields drops repeats within a row (compared trimmed). Group child fields append without de-duplication, since instance indexes must stay aligned across children; non-repeatable targets still take the first value of the last mapped column [@importer-service]. PID fields are the exception: values mapped onto a `pid` field are dropped with a per-row warning, because PIDs are system-managed — they are minted through the PID endpoints or automatically on publish, never imported [@import-tasks] [@pid-service]. On upsert-replace, stored PID values are preserved from the existing record.

Object imports may also carry one `media_selector`. This selector is separate from the metadata mapping and identifies a source column or XML element containing filenames. The UI can suggest a likely selector, but the user must select it explicitly. The backend rejects media selectors for non-object record types, missing selectors, and normalized filenames assigned to more than one source row [@importer-api] [@media-reference-service]. The dry-run result reports the number of rows with filenames, the total filenames, empty rows, and conflicts without writing references [@importer-api].

## Saved Import Mappings (Templates)

Configured mappings can be persisted as reusable templates in PostgreSQL (`import_mappings` table) [@importer-api] [@models]. In the Admin UI, catalogers can save the current mapping with a name, update existing templates, and load templates for the matching record type directly during upload or mapping [@importer-screen]. The API exposes CRUD endpoints under `/v1/importer/mappings`, and both `dry_run` and `import` accept an optional `mapping_id` to merge a stored template with any inline overrides [@importer-api]. The Admin UI sends only its visible mapping and omits `mapping_id`: loading a template copies the entries whose source columns exist in the uploaded file, and a server-side merge would restore the skipped columns and removed assignments. The loaded template's ID stays in the UI for the save dialog and is cleared on the next upload (`useImporterState.ts`). Alternatively, mappings can be exported and loaded as local JSON profile files or passed to the CLI command `katalon-manage import-xml`. The profile file loader sits in the mapping step (`StepMapping.tsx`, shared parser `readProfileFile` in `profileUtils.ts`); the upload-step button only shows once a file is uploaded, which XML imports never return to, because upload advances to the record-element step and back navigation stops there.

Issue #426 frames a future AI-assisted setup pass for the same pipeline rather than a second importer. The planned assistant would use uploaded sample data and the user-confirmed XML record root (nested JSON would first need its own import-scope decision) to propose field mappings, new field definitions, value transformations, and suspicious source values [@issue-426]. The non-negotiable boundary is that schema changes and the actual import remain explicit user decisions; AI suggestions may prepare an import profile, but they do not create fields or run imports autonomously [@issue-426].

## Background Import

The import endpoint serializes the mapping and queues `import_records_task` with record type, rows, ID number strategy, upsert strategy, auto-publish flag, user ID, subtype, fields to create, and the optional media selector [@importer-api]. The Celery task supports only the four primary inventory record types, validates subtype existence, creates requested field definitions in the selected subtype scope, and loads field definitions before applying the same mapping logic used in dry-run [@import-task].

During import, strict `vocab` field strings are resolved by `resolve_vocab_terms` against the configured vocabulary by a normalized key (`normalize_term_key`: NFKC, collapsed whitespace, casefold, so "Berlin" = " berlin "). A value matches a term by its code or by any of its language labels, so "Windows 2000" finds a curated term with code `system-162` instead of creating a duplicate; a label shared by several terms is reported as ambiguous for that row. The stored entry's label is the term's display label (German, then English, then code) [@import-resolution]. The request carries `vocab_modes` per target field: `extend` (default) creates missing terms and deduplicates variants within the file, `match_only` creates nothing, drops values without a matching term, and reports them as a task warning [@import-task] [@importer-api]. `vocab_free` fields are not resolved.

Top-level `relation` fields are resolved by `resolve_relations`. The request carries `relation_options` per target field: `lookup` is `idno` (default; exact ID number) or `label` (normalized title of the target record), `on_missing` is `error` (default; the row is reported and skipped) or `create` (a draft target with the text as its title, idno from the configured schema, an audit entry and an index update). The target type and subtype come from the field's `target_type`/`target_subtype`; the entry takes the field's `fixed_relation_type`, and a field without one is refused because the relation row would have no type. A label that matches several records is always an error, and a non-repeatable field accepts one value. Relation sub-fields inside groups are not resolved. `sync_schema_relations` then writes the `relations` rows from the resolved metadata [@import-resolution] [@import-task] [@importer-api]. Fuzzy (Levenshtein) matching against existing terms is deliberately not applied automatically. The task can generate ID numbers from configured schemas, skip, merge, or replace existing records by ID number, publish records when requested, write audit-log creation entries, and index changed records [@import-task]. After any create or update, it queues a bulk reindex for that record type so indexed documents converge with imported database state [@import-task].

When a media selector is present, the task stores one `MediaImportReference` per normalized filename and object. References are written for new objects and for existing objects reached through `skip`, `merge`, or `replace`. In the `skip` path, metadata remains unchanged while missing media references are added. The unique object-and-filename constraint and conflict-safe inserts make repeated imports idempotent. The task result reports the number of newly inserted references in `media_references_created` [@import-task] [@models].

Cancellation is cooperative. The API writes a Redis `cancel:<task_id>` key for one hour, and the task checks that key every ten rows before breaking with a warning [@importer-api] [@import-task].

After a terminal import result, the worker queues a concise result email to the triggering active staff user. The worker resolves the recipient from the stored user ID, so no address is included in the import task payload; failed notification enqueueing does not change the import result [@import-task] [@email-task].
