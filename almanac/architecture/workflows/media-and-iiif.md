---
title: "Media And IIIF"
summary: "Katalon's media workflow attaches image files to objects, validates and stores them, processes them through Celery and Cantaloupe, and exposes IIIF manifests to the portal."
topics: [architecture, workflows, media, iiif, celery, portal]
sources:
  - id: media-api
    type: file
    path: backend/src/katalon/api/v1/media.py
  - id: media-validation
    type: file
    path: backend/src/katalon/core/media_validation.py
  - id: cantaloupe
    type: file
    path: backend/src/katalon/integrations/cantaloupe.py
  - id: media-tasks
    type: file
    path: backend/src/katalon/workers/media_tasks.py
  - id: batch-service
    type: file
    path: backend/src/katalon/services/media_batch_import_service.py
  - id: iiif-viewer
    type: file
    path: frontend/portal/src/components/IIIFViewer.tsx
  - id: object-detail
    type: file
    path: frontend/portal/src/pages/ObjectDetailPage.tsx
---

Katalon's media workflow is object-only: media endpoints live under `/objects/{object_id}/media`, uploads require editor or admin rights, and public reads check object visibility before listing or serving files [@media-api]. Uploaded files are stored under `settings.media_root`, validated as real images with Pillow, represented by `MediaFile` rows, and handed to Celery for IIIF processing [@media-api] [@media-validation]. Cantaloupe supplies IIIF Image API URLs and image dimensions, while the portal consumes the resulting object manifest through a Clover IIIF viewer [@cantaloupe] [@iiif-viewer].

## Upload And Storage

`upload_media()` first verifies the target Object exists, rejects MIME types outside JPEG, PNG, TIFF, and WebP, streams the upload to `media_root`, and enforces `settings.max_upload_size_mb` while writing [@media-api]. After the file is on disk, `verified_image_mime()` opens it with Pillow, calls `image.verify()`, maps the detected image format back to an allowed MIME type, and rejects invalid or unsupported image content [@media-validation].

The created `MediaFile` starts with `status="pending"` and becomes primary when it is the object's first media file [@media-api]. The API commits before queueing `generate_iiif_tiles`, so the worker can load the row from its own database session [@media-api]. This is the queue boundary also covered by [Celery And Worker Queues](../backend/celery-and-worker-queues).

## Cantaloupe And Manifests

The media worker loads the `MediaFile`, derives the stored filename, and calls Cantaloupe's `/iiif/3/{filename}/info.json` endpoint to trigger lazy image processing and read dimensions [@media-tasks] [@cantaloupe]. Cantaloupe 4xx responses are treated as permanent errors and mark the media row `error`; other fetch failures return missing dimensions, so the worker still stores a manifest and marks the row `ready` unless an unexpected exception escapes into Celery retry handling [@media-tasks] [@cantaloupe].

For each successful file, the worker stores a single-canvas IIIF Presentation 3.0 manifest in `media.iiif_manifest` and marks the row `ready` [@media-tasks] [@cantaloupe]. Object-level manifests are built separately with one Canvas per media item, include object label, summary, configured metadata entries, homepage, and required inventory statement when those values are available [@cantaloupe]. This split lets stored per-file manifests support processing state while public object pages can expose a multi-canvas manifest.

## Public Reads And Portal Viewer

Media listing and raw file serving both call `ensure_publicly_visible()` for anonymous users before returning media for an object [@media-api]. `ObjectDetailPage` fetches the object, its media files, and relations, filters media to `status === "ready"`, then points the IIIF viewer at `/v1/objects/{id}/iiif/manifest` [@object-detail]. If the IIIF viewer fails, the page falls back to raw image files; if there is no ready media, it uses the configured placeholder image or a no-image state [@object-detail].

`IIIFViewer` fetches the manifest JSON itself and passes it to `@samvera/clover-iiif/viewer` with a minimal viewer configuration [@iiif-viewer]. The detail page also exposes the manifest URL as an alternate JSON-LD link and as a visible IIIF manifest link when ready media exists [@object-detail].

## Batch Media Import

The batch import endpoint accepts either a ZIP archive or multiple uploaded files, optionally with a CSV or TSV mapping file, and stages them under `media_root/_batch_imports/<job_id>` [@media-api]. `_safe_join()` resolves staged paths under the intended root and rejects archive entries that escape that directory [@media-api].

`import_media_batch_task` plans file-to-object matches from the mapping CSV or from UUIDs in parent folders and filenames, validates object IDs and optional `media_type` terms, copies accepted files into `media_root`, creates pending `MediaFile` rows, and queues the same `generate_iiif_tiles` task used by single uploads [@media-tasks] [@batch-service]. The batch task reports missing files, duplicate files, unmatched files, validation errors, and created counts, then removes the staging directory after completion or failure [@media-tasks].
