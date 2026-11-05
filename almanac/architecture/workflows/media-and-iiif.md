---
title: "Media And IIIF"
summary: "Katalon's media workflow attaches image and non-image files (PDF, audio, video, 3D) to objects, validates and stores them, routes images through Celery/Cantaloupe/IIIF, and dispatches portal viewers by MIME category."
topics: [architecture, workflows, media, iiif, celery, portal, s3, storage]
sources:
  - id: media-identifier-indexes
    type: file
    path: backend/migrations/versions/0084_media_identifier_indexes.py
  - id: media-identifier-index-tests
    type: file
    path: backend/tests/integration/test_media_identifier_indexes.py
  - id: thumbnail-tasks
    type: file
    path: backend/src/katalon/workers/thumbnail_tasks.py
  - id: thumbnail-api
    type: file
    path: backend/src/katalon/api/v1/thumbnail_warmup.py
  - id: media-api
    type: file
    path: backend/src/katalon/api/v1/media.py
  - id: media-service
    type: file
    path: backend/src/katalon/services/media_service.py
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
  - id: purge-tasks
    type: file
    path: backend/src/katalon/workers/purge_tasks.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: media-storage
    type: file
    path: backend/src/katalon/core/media_storage.py
  - id: management-cli
    type: file
    path: backend/src/katalon/management/cli.py
  - id: config
    type: file
    path: backend/src/katalon/config.py
  - id: compose
    type: file
    path: docker-compose.yml
  - id: nginx
    type: file
    path: docker/nginx.conf
  - id: compose-s3
    type: file
    path: docker-compose.s3.yml
  - id: admin-config
    type: file
    path: backend/src/katalon/api/v1/admin_config.py
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: media-lightbox
    type: file
    path: frontend/admin/src/components/MediaLightbox.tsx
  - id: iiif-viewer
    type: file
    path: frontend/portal/src/components/IIIFViewer.tsx
  - id: media-viewer
    type: file
    path: frontend/portal/src/components/MediaViewer.tsx
  - id: object-detail
    type: file
    path: frontend/portal/src/pages/ObjectDetailPage.tsx
  - id: portal-public
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
  - id: portal-config
    type: file
    path: backend/src/katalon/api/v1/portal.py
  - id: search-service
    type: file
    path: backend/src/katalon/services/search_service.py
  - id: backend-pyproject
    type: file
    path: backend/pyproject.toml
  - id: iiif-validator-issue
    type: issue
    url: https://github.com/karkraeg/Katalon/issues/408
---

Katalon's media workflow is object-only: media endpoints live under `/objects/{object_id}/media`, uploads require editor or admin rights, and public reads check object visibility before listing or serving files [@media-api]. Works, people, places, and collections do not have their own media upload surface; images that illustrate a work belong to an Object that is related to the Occurrence record [@media-api] [@screen-form]. Uploaded files are stored through a storage backend — local filesystem below `settings.media_root` by default, S3-compatible object storage as strict opt-in — validated, represented by `MediaFile` rows, and handed to Celery for IIIF processing *only when they are images* [@media-api] [@media-validation] [@media-storage]. Cantaloupe supplies IIIF Image API URLs and image dimensions for images, while the portal dispatches its viewer by `MediaFile.category`: Clover IIIF for images, a blob-backed iframe for PDF, HTML5 players for audio/video, and `@google/model-viewer` for 3D models [@cantaloupe] [@iiif-viewer] [@media-viewer] [@object-detail].

## Upload And Storage

`upload_media()` first verifies the target Object exists, rejects unsupported MIME types, streams the upload below `media_root`, and enforces `settings.max_upload_size_mb` while writing [@media-api]. The Python settings default is 100 MB, while the main Compose stack sets `MAX_UPLOAD_SIZE_MB` to 200 MB by default and the outer nginx accepts bodies up to 500 MB; large TIFF failures should therefore be checked against the application setting before changing nginx [@config] [@compose] [@nginx] [@media-api]. Each managed file stores a relative `storage_key`, not an absolute host path: the key is sharded by the first two hexadecimal UUID characters and its filename is `<media-uuid>--<safe-original-name>.<ext>`, for example `ab/ab12…--DSC-01374.jpg` [@media-storage] [@models]. Images (JPEG, including MPO camera files, PNG, TIFF, WebP) are validated with `verified_image_mime()` via Pillow `verify()`; non-image files (PDF, MP3/WAV/OGG, MP4/WebM, GLB/GLTF) are accepted without Pillow and stored under a `category` derived from their MIME type [@media-validation].

The storage-key migration converts a prior absolute path below the configured `MEDIA_ROOT` into its relative key without moving the file, so a historical flat filename remains readable as a valid key. An absolute path outside that root stops the migration instead of silently changing its location [@media-storage].

## Storage Backend (Local Or S3)

`get_storage()` in `media_storage` returns the configured backend: `LocalStorage` (default, files below `MEDIA_ROOT`, behavior unchanged) or `S3Storage` (opt-in via `STORAGE_BACKEND=s3`, targeting any S3-compatible implementation — Ceph RADOSGW, MinIO, Hetzner, Garage, AWS). Both implement the same protocol (`put_file`, `put_bytes`, `read_bytes`, `stream`, `delete`, `exists`) over the same relative sharded keys; `storage_key` and `pyramid_storage_key` are backend-agnostic, so IIIF identifiers and manifests are identical either way [@media-storage] [@config].

The S3 client is boto3 wrapped in `asyncio.to_thread`, deliberately deviating from boto3 defaults for compatibility: `request_checksum_calculation="when_required"` (botocore ≥ 1.36 otherwise sends `x-amz-checksum-crc32`, which many compatible implementations reject with 400), path-style addressing by default, an explicit region (RADOSGW ignores it, SigV4 requires a value), and configurable TLS verification for on-prem Ceph with internal CAs [@media-storage].

With S3 active, the API stages uploads in a temp file (MIME verification needs a seekable file) and then uploads, serves `/file` as a `StreamingResponse` straight from the bucket — no presigned URLs, so private media keep their visibility check — and the pyramid worker downloads the master into a temp file for `pyvips` (it needs random access), runs the unchanged `_make_pyramid_tiff`, and uploads the pyramid; a missing master falls back to the original exactly like a missing local file [@media-api] [@media-tasks]. The local backend keeps its direct streaming paths.

Cantaloupe reads from the bucket via its native `S3Source` (wired in `docker-compose.s3.yml`), so tile delivery never passes through the API. Cantaloupe 5.0.x S3Source has no path-style option and always uses virtual-hosted addressing, which means `<bucket>.<endpoint-host>` must resolve — wildcard DNS on the gateway in production, or a Compose network alias for the dev MinIO override. The `MEDIA_ROOT` mounts stay in place because logos and portal themes remain local files [@media-storage] [@compose-s3].

Image uploads start with `status="pending"`; non-image uploads start ready. A new `MediaFile` becomes primary when it is the object's first media file [@media-api]. For images, the API commits before queueing `generate_iiif_tiles`, so the worker can load the row from its own database session [@media-api]. This is the queue boundary also covered by [Celery And Worker Queues](../backend/celery-and-worker-queues).

Single uploads, media metadata changes (including rights, visibility and primary selection), and deletion move the object's `updated_at` through `media_service.touch_object()`. Non-image uploads, edits and deletion reindex the object through the API; image uploads are reindexed when the worker marks the image `ready`, which moves the datestamp again. Incremental OAI harvests can therefore pick up media-only changes [@media-service] [@media-api] [@media-tasks].

## Rights Per Media File

License URI and rights holder belong to each `MediaFile`. Administrators may set instance defaults; single and batch uploads copy them into each new file, so later default changes do not alter existing files. The admin form keeps these optional fields in the file's collapsible `Rechteangaben` section; present values are summarized while collapsed [@media-api] [@screen-form] [@admin-config]. A free-text `credit_line` (permission note such as "Veröffentlichung genehmigt von …") sits next to them; it is not a rights holder name. The portal shows it in the media rights block, LIDO exports it as `rightsResource/creditLine`. Changing license, rights holder or credit line bumps the object's `updated_at` and reindexes it, so OAI harvesters see the change.

## Cantaloupe And Manifests

Before calling Cantaloupe, the media worker converts the stored original into a tiled, pyramidal TIFF via `pyvips` (`tile=True, pyramid=True, compression="jpeg", Q=85`) so Cantaloupe's `Java2dProcessor` gets random access into the right resolution level instead of decoding the full source image on every tile/zoom request [@media-tasks]. The pyramid is written next to the original as `<media-uuid>--<safe-original-name>_pyramid.tif` and its relative key is recorded in `MediaFile.iiif_storage_key`; the original file itself is untouched and stays the download source [@media-tasks] [@models]. If the conversion fails (unreadable source, missing `libvips`, unexpected `pyvips` error), the worker logs a warning and falls back to the original file — `iiif_storage_key` stays `NULL` and Cantaloupe reads the flat original with its usual (slower) full-decode behaviour [@media-tasks].

The worker then derives the relative storage key — the pyramid's if one exists, otherwise the original's — URL-encodes it as one IIIF identifier (including the shard separator), and calls Cantaloupe's `/iiif/3/{key}/info.json` endpoint to trigger lazy image processing and read dimensions [@media-tasks] [@cantaloupe]. Cantaloupe 4xx responses are treated as permanent errors and mark the media row `error`; other fetch failures return missing dimensions, so the worker still marks the row `ready` unless an unexpected exception escapes into Celery retry handling [@media-tasks] [@cantaloupe].

For each successful file, the worker stores image dimensions and marks the row `ready`; it does not persist a manifest with absolute URLs [@media-tasks]. Object-level manifests are built on request with one Canvas per media item, using the current public IIIF URL and stored dimensions. They include object label, summary, configured metadata entries, homepage, and required inventory statement when those values are available [@cantaloupe]. All IIIF-facing identifiers — object manifests, the media list's `_links.thumbnail`, and the portal thumbnail redirect — resolve to `iiif_storage_key` when set, falling back to `storage_key` otherwise, so Cantaloupe receives the required relative path [@cantaloupe] [@media-api].

The current test coverage checks manifest structure with local assertions and Cantaloupe helper behavior, but the open IIIF validation task is to run Katalon's Image API and Presentation API output through the official validators and then either fix deviations or record accepted ones [@cantaloupe] [@iiif-validator-issue].

Deleting a `MediaFile` and purging a soft-deleted object both remove the pyramid alongside the original when `iiif_storage_key` is set [@media-api] [@purge-tasks].

## Thumbnail Warm-Up

After image processing, `warm_thumbnails` requests the 300 and 600 px JPEG derivatives directly from Cantaloupe. `katalon-manage warm-thumbnails` or the admin-only `POST /v1/admin/thumbnails/warm` starts a resumable bulk run, primary images first; `GET` on that path reports progress. The start and each batch share a token-owned Redis lock acquired before state initialization and renewed by the existing lease watchdog. Competing starts only report progress; overlapping batches do no work. Only the lock owner writes the cursor and counters, and successors are dispatched after the lock is released. A separate expiring marker covers time spent waiting in the queue; after a crashed batch or lost message, starting again resumes from the persisted cursor [@thumbnail-tasks] [@thumbnail-api].

## Non-Image Media And Viewer Dispatch

Non-image files never enter the Cantaloupe/IIIF pipeline. The upload path assigns a `category` (`image`/`pdf`/`audio`/`video`/`3d`) and, because there is no tiling step, the media row is marked `ready` immediately [@media-api]. `_links.thumbnail` and the IIIF manifest are only produced for image files, so portal thumbnails and manifests skip non-image media [@media-api] [@cantaloupe].

`ObjectDetailPage` picks a viewer from `selectedMedia.category`: images use the IIIF viewer, other categories render through `MediaViewer`, which fetches PDFs as blobs before handing them to an iframe because the file endpoint serves downloads, or chooses an HTML5 `<audio>`/`<video>` element or a lazy-loaded `@google/model-viewer` component [@object-detail] [@media-viewer]. There is deliberately no transcoding — only pre-encoded files are accepted, and presentation derivatives remain out of scope.

The admin record form accepts PDFs and displays them in the media grid as a file tile with a `PDF` label; it does not embed a PDF preview inside the form grid [@screen-form]. Full PDF display is covered by the admin lightbox, whose `pdf` branch renders an iframe, and by the portal viewer described above [@media-lightbox] [@media-viewer]. PDF text is not part of the search index: `build_index_doc()` builds `search_text` from public metadata, relation titles, and identifiers, while media contributes only the primary media id and image dimensions [@search-service]. No PDF text extraction dependency such as `pypdf`, `pymupdf`, or `pdfminer` is present in the backend package definition [@backend-pyproject].

## Public Reads And Portal Viewer

The IIIF authorization lookup matches either `storage_key` or `iiif_storage_key` and excludes deleted media. Both identifier columns have separate non-unique B-tree indexes, allowing PostgreSQL to combine index scans for the OR predicate. Migration `0084` builds them concurrently so existing media writes can continue; a representative 10,000-row integration test checks both lookup branches and deleted/missing identifiers without disabling sequential scans. Small tables may still use a sequential scan when the planner estimates that it is cheaper [@media-api] [@models] [@media-identifier-indexes] [@media-identifier-index-tests].

The migration owns only `ix_media_files_storage_key` and `ix_media_files_iiif_storage_key`. Existing operator-created `perf_*` indexes are not removed; equivalent indexes can consume extra space and write work and should be reviewed separately. When an online migration is retried after an interrupted concurrent build, it checks `pg_index.indisvalid`, drops only invalid indexes with those two core names concurrently, and rebuilds them. Existing valid core indexes are retained. Offline SQL generation cannot inspect the catalog, so invalid indexes must be checked separately before applying generated SQL [@media-identifier-indexes].

Media listing and raw file serving both call `ensure_publicly_visible()` for anonymous users before returning media for an object [@media-api]. `ObjectDetailPage` fetches the object, its media files, and relations, filters media to `status === "ready"`, then points the IIIF viewer at `/v1/objects/{id}/iiif/manifest` [@object-detail]. If the IIIF viewer fails, the page falls back to IIIF thumbnails; if there is no ready media, it uses the configured placeholder image or a no-image state [@object-detail].

Visibility is also gated per file: `MediaFile.is_public` (default `true`) lets an otherwise-public object keep individual images hidden from anonymous users — metadata and other media files stay visible. Anonymous listing/serving/manifest queries add an `is_public` filter alongside the `status == "ready"` check [@media-api]. Because Cantaloupe itself has no authentication, `docker/nginx.conf` runs an `auth_request` in front of `/iiif/` that calls a dedicated, unauthenticated-router backend endpoint (`GET /v1/media/_authorize`) on every tile/derivative request; it resolves the IIIF identifier back to a `MediaFile`, re-checks `ensure_publicly_visible()` and `is_public`, and returns 403 before nginx ever proxies to Cantaloupe [@media-api]. The admin thumbnail grid fetches images via `authorizedFetch()` into a blob (`ImageThumb`, mirroring the existing `VideoThumb` pattern) rather than a plain `<img src>`, since only an authenticated fetch can carry the bearer token past that gate; the thumbnail redirect endpoint therefore redirects to a host-relative `/iiif/...` path instead of the absolute Cantaloupe base URL, so the redirect stays same-origin and the browser keeps the `Authorization` header [@media-api] [@screen-form]. See [Cantaloupe Auth Gate](../../decisions/operations/cantaloupe-auth-gate) for the full rationale. The same endpoint answers with `X-Media-Visibility: public|restricted` (public = `is_public` media of a non-deleted object in a public status, i.e. what anonymous visitors may see); nginx takes it via `auth_request_set`, drops Cantaloupe's own `Cache-Control` and sets `public, max-age=2592000` or `private, max-age=86400`. A 403 carries no cache header. Cantaloupe itself is configured `CANTALOUPE_CACHE_CLIENT_PUBLIC=false`/`PRIVATE=true`, so deployments without this nginx rule (Helm/ingress-nginx, which cannot rewrite the header without snippets) fall back to `private` rather than letting shared caches keep internal derivatives. Because a location-level `add_header` replaces the server-level ones, the `/iiif/` location repeats the security headers [@nginx] [@media-api].

`IIIFViewer` fetches the manifest JSON itself and passes it to `@samvera/clover-iiif/viewer` with a minimal viewer configuration [@iiif-viewer]. Portal cards, result rows, and media strips request the 300 px JPEG IIIF derivative (`/iiif/3/<identifier>/full/,300/0/default.jpg`) directly: the search document carries `primary_media_iiif` and the media list `iiif_identifier`, so each thumbnail costs one request, still gated by the `/iiif/` auth_request (`utils/thumbnails.ts`) [@media-api] [@portal-public]. Teaser lists that start from IDs rather than search hits (home page objects, objects linked to an entity/place/occurrence, collection members) load all objects plus their preview file with one `GET /portal/v1/objects/summaries?ids=…` request (at most 100 IDs; the client splits larger lists) through `loadObjectTeasers()`, instead of an object and a media read per teaser. The preview is the ready primary file, otherwise the oldest ready one; anonymous callers only get `is_public` files. Hidden or deleted IDs are skipped, and the order of the request is kept [@portal-public] [@media-api]. Without an identifier (documents indexed before it existed) the portal falls back to the thumbnail route, which redirects (307) to the same derivative with `Cache-Control: private, max-age=THUMBNAIL_REDIRECT_MAX_AGE` (30 days); caching the redirect is safe because the image fetch behind it is authorized every time, and `private` because staff receive redirects to internal media. Error responses carry no cache header [@media-api]. Derivative sizes are defined once in `core/thumbnails.py` and mirrored in the portal; a test keeps both in sync. Result grids and other tile views render thumbnails through `components/LazyImage.tsx`: an IntersectionObserver with `rootMargin: 200% 0px` sets `src` about two screen heights ahead (native `loading="lazy"` only as fallback), `decoding="async"`, intrinsic `width`/`height` from `media_width`/`media_height`, a `srcset` with the 600 px derivative for high-density screens, and the first eight results load eagerly with `fetchpriority="high"`. The detail page always exposes the manifest URL as an alternate JSON-LD link, and additionally renders it as a visible, icon-free link/button plus a copy-URL action when `PortalConfig.show_iiif_manifest_link` is enabled (default `true`) and ready image media exists; disabling the setting in Admin → Einstellungen hides both, leaving the JSON-LD link untouched [@object-detail] [@portal-config].

## Batch Media Import

The batch import endpoint accepts either a ZIP archive or multiple uploaded files, optionally with a CSV or TSV mapping file, and stages them under `media_root/_batch_imports/<job_id>` [@media-api]. `_safe_join()` resolves staged paths under the intended root and rejects archive entries that escape that directory [@media-api]. Object metadata imports can prepare this step by storing pending `MediaImportReference` rows from a user-selected filename column or XML element [@importer-task] [@models].

`import_media_batch_task` applies explicit CSV assignments first. Files not named in a valid CSV are matched against pending media references by normalized basename; files without a reference fall back to UUIDs in parent folders or filename prefixes [@media-tasks] [@batch-service]. An invalid mapping CSV blocks automatic processing, and conflicting CSV targets or references to several objects are reported instead of choosing one target [@media-tasks].

For an already populated database plus an external media directory, the durable contract is that Katalon must still receive Katalon object UUIDs somewhere in the batch job. The management CLI exposes metadata imports with `--media-selector`, but it does not expose a command that reads an existing media directory and attaches files directly [@management-cli]. Without previously created `MediaImportReference` rows, operators need a mapping file whose `filename`/`file`/`dateiname` column resolves to a unique staged basename and whose `object_id`/`object`/`objekt_id`/`id` column contains the Katalon object UUID; external legacy identifiers such as CollectiveAccess object ids or `idno` values must be translated to Katalon UUIDs before the batch media task runs [@batch-service] [@media-tasks].

After resolving an object, the task validates its ID and any optional `media_type`, copies the image to the same sharded managed-key layout as a single upload, verifies its MIME type, creates a pending `MediaFile`, and queues the same `generate_iiif_tiles` task used by single uploads [@media-tasks] [@media-storage]. A pending media reference is deleted only after the corresponding `MediaFile` has been created successfully in the same database transaction. Failed files retain their references for a later retry [@media-tasks]. The result reports missing files, duplicate files, unmatched files, validation errors, and created counts; the staged job directory is removed after completion or failure [@media-tasks].
