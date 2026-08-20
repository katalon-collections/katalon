---
title: "Media And IIIF"
summary: "Katalon's media workflow attaches image and non-image files (PDF, audio, video, 3D) to objects, validates and stores them, routes images through Celery/Cantaloupe/IIIF, and dispatches portal viewers by MIME category."
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
  - id: importer-task
    type: file
    path: backend/src/katalon/workers/import_tasks.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: admin-config
    type: file
    path: backend/src/katalon/api/v1/admin_config.py
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: iiif-viewer
    type: file
    path: frontend/portal/src/components/IIIFViewer.tsx
  - id: media-viewer
    type: file
    path: frontend/portal/src/components/MediaViewer.tsx
  - id: object-detail
    type: file
    path: frontend/portal/src/pages/ObjectDetailPage.tsx
---

Katalon's media workflow is object-only: media endpoints live under `/objects/{object_id}/media`, uploads require editor or admin rights, and public reads check object visibility before listing or serving files [@media-api]. Uploaded files are stored under `settings.media_root`, validated, represented by `MediaFile` rows, and handed to Celery for IIIF processing *only when they are images* [@media-api] [@media-validation]. Cantaloupe supplies IIIF Image API URLs and image dimensions for images, while the portal dispatches its viewer by `MediaFile.category`: Clover IIIF for images, a blob-backed iframe for PDF, HTML5 players for audio/video, and `@google/model-viewer` for 3D models [@cantaloupe] [@iiif-viewer] [@media-viewer] [@object-detail].

## Upload And Storage

`upload_media()` first verifies the target Object exists, rejects unsupported MIME types, streams the upload to `media_root`, and enforces `settings.max_upload_size_mb` while writing [@media-api]. Images (JPEG, PNG, TIFF, WebP) are validated with `verified_image_mime()` via Pillow `verify()`; non-image files (PDF, MP3/WAV/OGG, MP4/WebM, GLB/GLTF) are accepted without Pillow and stored under a `category` derived from their MIME type [@media-validation].

The created `MediaFile` starts with `status="pending"` and becomes primary when it is the object's first media file [@media-api]. The API commits before queueing `generate_iiif_tiles`, so the worker can load the row from its own database session [@media-api]. This is the queue boundary also covered by [Celery And Worker Queues](../backend/celery-and-worker-queues).

## Rights Per Media File

License URI and rights holder belong to each `MediaFile`. Administrators may set instance defaults; single and batch uploads copy them into each new file, so later default changes do not alter existing files. The admin form keeps these optional fields in the file's collapsible `Rechteangaben` section; present values are summarized while collapsed [@media-api] [@screen-form] [@admin-config].

## Cantaloupe And Manifests

The media worker loads the `MediaFile`, derives the stored filename, and calls Cantaloupe's `/iiif/3/{filename}/info.json` endpoint to trigger lazy image processing and read dimensions [@media-tasks] [@cantaloupe]. Cantaloupe 4xx responses are treated as permanent errors and mark the media row `error`; other fetch failures return missing dimensions, so the worker still stores a manifest and marks the row `ready` unless an unexpected exception escapes into Celery retry handling [@media-tasks] [@cantaloupe].

For each successful file, the worker stores a single-canvas IIIF Presentation 3.0 manifest in `media.iiif_manifest` and marks the row `ready` [@media-tasks] [@cantaloupe]. Object-level manifests are built separately with one Canvas per media item, include object label, summary, configured metadata entries, homepage, and required inventory statement when those values are available [@cantaloupe]. This split lets stored per-file manifests support processing state while public object pages can expose a multi-canvas manifest.

## Non-Image Media And Viewer Dispatch

Non-image files never enter the Cantaloupe/IIIF pipeline. The upload path assigns a `category` (`image`/`pdf`/`audio`/`video`/`3d`) and, because there is no tiling step, the media row is marked `ready` immediately [@media-api]. `_links.thumbnail` and the IIIF manifest are only produced for image files, so portal thumbnails and manifests skip non-image media [@media-api] [@cantaloupe].

`ObjectDetailPage` picks a viewer from `selectedMedia.category`: images use the IIIF viewer, other categories render through `MediaViewer`, which fetches PDFs as blobs before handing them to an iframe because the file endpoint serves downloads, or chooses an HTML5 `<audio>`/`<video>` element or a lazy-loaded `@google/model-viewer` component [@object-detail] [@media-viewer]. There is deliberately no transcoding — only pre-encoded files are accepted, and presentation derivatives remain out of scope.

## Public Reads And Portal Viewer

Media listing and raw file serving both call `ensure_publicly_visible()` for anonymous users before returning media for an object [@media-api]. `ObjectDetailPage` fetches the object, its media files, and relations, filters media to `status === "ready"`, then points the IIIF viewer at `/v1/objects/{id}/iiif/manifest` [@object-detail]. If the IIIF viewer fails, the page falls back to raw image files; if there is no ready media, it uses the configured placeholder image or a no-image state [@object-detail].

`IIIFViewer` fetches the manifest JSON itself and passes it to `@samvera/clover-iiif/viewer` with a minimal viewer configuration [@iiif-viewer]. The detail page also exposes the manifest URL as an alternate JSON-LD link and as a visible IIIF manifest link when ready media exists [@object-detail].

## Batch Media Import

The batch import endpoint accepts either a ZIP archive or multiple uploaded files, optionally with a CSV or TSV mapping file, and stages them under `media_root/_batch_imports/<job_id>` [@media-api]. `_safe_join()` resolves staged paths under the intended root and rejects archive entries that escape that directory [@media-api]. Object metadata imports can prepare this step by storing pending `MediaImportReference` rows from a user-selected filename column or XML element [@importer-task] [@models].

`import_media_batch_task` applies explicit CSV assignments first. Files not named in a valid CSV are matched against pending media references by normalized basename; files without a reference fall back to UUIDs in parent folders or filename prefixes [@media-tasks] [@batch-service]. An invalid mapping CSV blocks automatic processing, and conflicting CSV targets or references to several objects are reported instead of choosing one target [@media-tasks].

After resolving an object, the task validates its ID and any optional `media_type`, copies the image into `media_root`, verifies its MIME type, creates a pending `MediaFile`, and queues the same `generate_iiif_tiles` task used by single uploads [@media-tasks]. A pending media reference is deleted only after the corresponding `MediaFile` has been created successfully in the same database transaction. Failed files retain their references for a later retry [@media-tasks]. The result reports missing files, duplicate files, unmatched files, validation errors, and created counts; the staged job directory is removed after completion or failure [@media-tasks].
