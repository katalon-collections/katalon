---
title: "Celery And Worker Queues"
summary: "Katalon uses Redis-backed Celery workers for media processing, imports, search indexing, reconciliation, and cleanup, with different enqueue behavior for fire-and-forget work and client-polled jobs."
topics: [architecture, workers, media, importer, search, operations]
sources:
  - id: celery-app
    type: file
    path: backend/src/katalon/workers/celery_app.py
  - id: enqueue
    type: file
    path: backend/src/katalon/workers/enqueue.py
  - id: media-tasks
    type: file
    path: backend/src/katalon/workers/media_tasks.py
  - id: import-tasks
    type: file
    path: backend/src/katalon/workers/import_tasks.py
  - id: index-tasks
    type: file
    path: backend/src/katalon/workers/index_tasks.py
  - id: cleanup-tasks
    type: file
    path: backend/src/katalon/workers/cleanup_tasks.py
  - id: compose
    type: file
    path: docker-compose.yml
---

Katalon uses Celery for background work that would be too slow or unreliable inside HTTP request handling. The Celery app uses `settings.redis_url` as both broker and result backend, includes media, index, import, and cleanup task modules, serializes tasks as JSON, tracks started tasks, and acknowledges tasks late [@celery-app]. In Compose, the worker and beat services run from the backend worker image with the same database, Redis, Elasticsearch, Cantaloupe, media, and secret settings used by the API service [@compose].

## Queue Configuration

The Celery app is named `katalon` and imports four task modules: `media_tasks`, `index_tasks`, `import_tasks`, and `cleanup_tasks` [@celery-app]. Celery beat schedules a daily reconciliation count job at 03:00 and a weekly ID-diff reconciliation job at 04:00 on Sunday [@celery-app]. Those scheduled jobs use the same task app as request-triggered background work.

Worker tasks open their own async database sessions. Media tasks and index tasks create async SQLAlchemy engines with `NullPool` so connections are not reused across Celery event loops [@media-tasks] [@index-tasks]. Import tasks use the same pattern and explicitly dispose the engine after their event loop closes [@import-tasks].

## Enqueue Policy

Katalon has two enqueue helpers because not every background task has the same user-facing contract. `enqueue()` swallows broker errors, logs a warning, and returns `None`; it is for fire-and-forget work where the primary database write has already succeeded [@enqueue]. `enqueue_or_503()` raises HTTP 503 when the broker is unavailable; it is for endpoints that return a job id the client must poll [@enqueue].

The helper docstring states the operational decision behind this split: reindexing, tile generation, and relation cleanup should not turn a successful HTTP write into a 500 when Redis is down, but media batch import and record import need a broker because the client receives and polls a task id [@enqueue].

## Media Tasks

`generate_iiif_tiles` loads a `MediaFile`, asks Cantaloupe for image info, builds an IIIF manifest, marks the media row `ready`, and stores the manifest JSON [@media-tasks]. If Cantaloupe returns a domain error, the task marks the media row `error`; for other exceptions it retries up to three times and marks the row `error` after the final retry [@media-tasks].

`import_media_batch_task` processes a staged job directory with `images/` and optional `mapping.csv`, validates filenames, object ids, media type vocabulary terms, and image MIME types, copies accepted files into `MEDIA_ROOT`, creates `MediaFile` rows, and dispatches IIIF tile generation for each created file [@media-tasks]. It updates Celery state while processing and removes the staged job directory after success or failure [@media-tasks].

## Import Tasks

`import_records_task` imports CSV or Excel rows into object, entity, place, or occurrence records [@import-tasks]. It validates subtype, can create field definitions requested with the import, applies column mappings, resolves vocabulary terms by looking up or creating terms, handles id number strategies, supports skip/merge/replace upserts by idno, validates metadata, writes audit entries, indexes records, optionally publishes records, and records warnings for audit or indexing failures [@import-tasks].

The import task supports cancellation through Redis. It checks a `cancel:<task-id>` key every ten rows and stops with a warning when that key is present [@import-tasks]. After any created or updated rows, it tries to dispatch a bulk reindex for the affected type, but broker failure in that post-import dispatch is swallowed [@import-tasks].

## Search And Cleanup Tasks

Search tasks cover single-record indexing, deletion from Elasticsearch, cascade reindexing, per-type reindexing, reconciliation, dispatch-based indexing, and full reindexing [@index-tasks]. `index_record_task` retries Elasticsearch failures and writes a permanent `index_failed` audit entry after max retries [@index-tasks]. `cascade_reindex_task` reindexes records that link to the changed record so inherited or embedded relation data stays searchable [@index-tasks].

Reconciliation compares database counts and Elasticsearch counts by record type, optionally falls through to ID-diff mode, dispatches indexing for missing records, and removes stale Elasticsearch ids [@index-tasks]. Cleanup tasks remove dangling relation-field references from JSONB metadata after a target record is deleted by scanning active relation field definitions and rewriting affected metadata values [@cleanup-tasks].

## Related Pages

Worker queues are part of the [System Overview](../system/system-overview). The enqueue helper is the runtime basis for the [Broker-Tolerant Enqueue](../../decisions/operations/broker-tolerant-enqueue) decision.
