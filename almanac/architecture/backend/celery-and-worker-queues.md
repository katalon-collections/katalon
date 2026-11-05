---
title: "Celery And Worker Queues"
summary: "Katalon uses Redis-backed Celery workers for media processing, imports, batch edits, search indexing, RDF sync, reconciliation, purge, email, and health heartbeat work, with different enqueue behavior for fire-and-forget work and client-polled jobs."
topics: [architecture, workers, media, importer, search, operations]
sources:
  - id: isolated-session
    type: file
    path: backend/src/katalon/core/isolated_session.py
  - id: thumbnail-tasks
    type: file
    path: backend/src/katalon/workers/thumbnail_tasks.py
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
  - id: purge-tasks
    type: file
    path: backend/src/katalon/workers/purge_tasks.py
  - id: rdf-tasks
    type: file
    path: backend/src/katalon/workers/rdf_tasks.py
  - id: relation-cleanup
    type: file
    path: backend/src/katalon/services/relation_cleanup_service.py
  - id: email-tasks
    type: file
    path: backend/src/katalon/workers/email_tasks.py
  - id: compose
    type: file
    path: docker-compose.yml
---

Katalon uses Celery for background work that would be too slow or unreliable inside HTTP request handling. The Celery app uses `settings.redis_url` as both broker and result backend, includes media, index, import, and cleanup task modules, serializes tasks as JSON, tracks started tasks, and acknowledges tasks late [@celery-app]. In Compose, the worker and beat services run from the backend worker image with the same database, Redis, Elasticsearch, Cantaloupe, media, and secret settings used by the API service [@compose].

## Queue Configuration

The Celery app is named `katalon` and imports media, index, import, batch, purge, email, RDF, and health task modules [@celery-app]. Celery beat schedules a daily reconciliation count job at 03:00, a weekly ID-diff reconciliation job at 04:00 on Sunday, a daily soft-delete purge at 05:00, a pending-media-delete sweep every 15 minutes, and a heartbeat every two minutes [@celery-app]. Those scheduled jobs use the same task app as request-triggered background work.

## Email Tasks

`send_email` accepts JSON-serializable recipient, subject, text, and optional HTML arguments. `send_password_reset_email` accepts only a reset-token row UUID, reads and decrypts the delivery token after the broker boundary, then calls the same SMTP path. When SMTP is enabled it uses Python's standard-library SMTP client and sends a multipart text/HTML message; when SMTP is disabled it records a skipped delivery. SMTP failures are logged without credentials and fail the task rather than an HTTP request [@email-tasks].

Worker tasks open their own async database sessions through `katalon.core.isolated_session` (`make_session`, `engine_scope`, `isolated_session`): a per-run `NullPool` engine whose connections carry `application_name = katalon-worker` in `pg_stat_activity`, disposed when the task's event loop ends [@isolated-session]. Workers never import `katalon.database` (the pooled global engine binds connections to the loop that opened them and leaves them open server-side); `test_architecture.py` enforces this for direct imports. The registry loaders in `authority_service` and `metadata_format_service` use the same helper (`katalon-registry`). The streaming reindex builds records on up to 16 concurrent sessions inside an `asyncio.TaskGroup`, so a failing build cancels and awaits its siblings before the sessions close; with plain `gather` the cancelled siblings leaked their connections as `idle in transaction` until the worker restarted [@index-tasks]. Media, import, RDF and thumbnail tasks follow the same pattern [@media-tasks] [@import-tasks] [@rdf-tasks].

## Enqueue Policy

Katalon has three enqueue primitives because not every background task has the same user-facing contract or the same relationship to the request's database transaction. `enqueue()` swallows broker errors, logs a warning, and returns `None`; it dispatches immediately and is only safe once the caller already knows the referenced row is durably committed [@enqueue]. `enqueue_or_503()` raises HTTP 503 when the broker is unavailable; it is for endpoints that return a job id the client must poll [@enqueue]. `after_commit(db, task, ...)` defers an `enqueue()` call by recording it on the SQLAlchemy session instead of dispatching it — the request/task's commit path only turns it into a real `.delay()` once `db.commit()` has actually succeeded, and a rollback silently drops it (#392) [@enqueue].

Before #392, several call sites (single-record ES indexing/removal on CRUD, publish, and restore; relation cleanup after delete; per-file IIIF tile dispatch during batch media import; and the schema-change reindex trigger) called `enqueue()` directly while the row they referenced was still an uncommitted write in the same request, relying on the fact that `katalon.database.get_db` commits the session after the endpoint returns. A later rollback in the same request could still leave an already-dispatched Celery task expecting a row that was never written. Those call sites now register through `after_commit`; `DatabaseCommitMiddleware` and `katalon.database.get_db` drain the deferred calls immediately after `session.commit()` succeeds (which occurs before HTTP response headers are transmitted to prevent read-after-write races), and Celery-task-owned sessions (batch edit, record import, IIIF tile generation) call `run_after_commit_hooks(session)` explicitly right after their own `session.commit()` [@enqueue].


## Media Tasks

`generate_iiif_tiles` loads a `MediaFile`, asks Cantaloupe for image info, builds an IIIF manifest for its task result, stores image dimensions, and marks the media row `ready`. The manifest JSON is not stored in the database [@media-tasks]. If Cantaloupe returns a domain error, the task marks the media row `error`; for other exceptions it retries up to three times and marks the row `error` after the final retry [@media-tasks].

After an image becomes `ready`, `generate_iiif_tiles` enqueues `katalon.media.warm_thumbnails` for it, which requests every portal thumbnail size (`core/thumbnails.py`: 300 px and 600 px high) from Cantaloupe directly so the derivatives sit in its disk cache before the first visitor asks [@thumbnail-tasks]. The bulk variant `katalon.media.warm_thumbnails_bulk` (started by `katalon-manage warm-thumbnails`, `katalon media warm-thumbnails` or `POST /v1/admin/thumbnails/warm`) is a chain of short batch tasks (`THUMBNAIL_WARM_BATCH_SIZE`, default 100) with `THUMBNAIL_WARM_CONCURRENCY` (default 3) parallel Cantaloupe requests: primary images first (keyset over `media_files.id`), then the rest. Only one chain runs at a time (Redis lease `katalon:thumbwarm:lease`), so the run never uses more Cantaloupe cores than configured, and no single task outlives Redis' visibility timeout. Phase and last id live in `katalon:thumbwarm:state`; starting again after a crash resumes from there, `--restart` starts over and makes batches of the old run stop as `superseded` [@thumbnail-tasks].

`import_media_batch_task` processes a staged job directory with `images/` and optional `mapping.csv`, validates filenames, object ids, media type vocabulary terms, and image MIME types, copies accepted files into `MEDIA_ROOT`, creates `MediaFile` rows, and dispatches IIIF tile generation for each created file [@media-tasks]. It updates Celery state while processing and removes the staged job directory after success or failure [@media-tasks].

## Import Tasks

`import_records_task` imports CSV or Excel rows into object, entity, place, or occurrence records [@import-tasks]. It validates subtype, can create field definitions requested with the import, applies column mappings, resolves vocabulary terms by looking up or creating terms, handles id number strategies, supports skip/merge/replace upserts by idno, validates metadata, writes audit entries, indexes records, optionally publishes records, and records warnings for audit or indexing failures [@import-tasks].

The import task supports cancellation through Redis. It checks a `cancel:<task-id>` key every ten rows and stops with a warning when that key is present [@import-tasks]. After any created or updated rows, it tries to dispatch a bulk reindex for the affected type, but broker failure in that post-import dispatch is swallowed [@import-tasks].

## Search And Cleanup Tasks

Search tasks cover single-record indexing, deletion from Elasticsearch, cascade reindexing, per-type reindexing, reconciliation, dispatch-based indexing, and full reindexing [@index-tasks]. `index_record_task` retries Elasticsearch failures and writes a permanent `index_failed` audit entry after max retries [@index-tasks]. `cascade_reindex_task` reindexes records that link to the changed record so inherited or embedded relation data stays searchable [@index-tasks].

Reconciliation compares database counts and Elasticsearch counts by record type, optionally falls through to ID-diff mode, dispatches indexing for missing records, and removes stale Elasticsearch ids [@index-tasks]. The daily purge job reads its retention window and on/off switch from `AdminConfig` (`purge_retention_days`, `auto_purge_enabled` — admin-configurable, no restart needed) rather than a static setting, skips the run entirely when disabled, hard-deletes soft-deleted records past the retention window, and retries physical media deletion after committed delete intent; relation-field cleanup lives in `relation_cleanup_service.py`, which scans active relation field definitions and rewrites affected JSONB metadata after a target record is deleted [@purge-tasks] [@relation-cleanup]. The same per-record hard-delete logic backs an on-demand admin `POST /{id}/purge` endpoint for immediately purging one trashed record outside the nightly schedule (#414).

## Related Pages

Worker queues are part of the [System Overview](../system/system-overview). The enqueue helper is the runtime basis for the [Broker-Tolerant Enqueue](../../decisions/operations/broker-tolerant-enqueue) decision.
