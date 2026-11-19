---
title: "File Field Attachments"
summary: "The `file` schema field type stores attachments in their own `attachments` table, references them by id in record metadata, checks references on save, and serves them to the Admin and the Portal under different rules."
topics: [concepts, metadata, schema, media, portal, security]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: migration
    type: file
    path: backend/migrations/versions/0088_attachments.py
  - id: attachment-service
    type: file
    path: backend/src/katalon/services/attachment_service.py
  - id: media-api
    type: file
    path: backend/src/katalon/api/v1/media.py
  - id: attachments-api
    type: file
    path: backend/src/katalon/api/v1/attachments.py
  - id: portal-public
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
  - id: public-metadata
    type: file
    path: backend/src/katalon/services/public_metadata_service.py
  - id: schema-service
    type: file
    path: backend/src/katalon/services/schema_service.py
  - id: schema-admin
    type: file
    path: backend/src/katalon/api/v1/schema_admin.py
  - id: purge-tasks
    type: file
    path: backend/src/katalon/workers/purge_tasks.py
  - id: procedures-api
    type: file
    path: backend/src/katalon/api/v1/procedures.py
  - id: cli
    type: file
    path: backend/src/katalon/management/cli.py
  - id: config
    type: file
    path: backend/src/katalon/config.py
  - id: media-validation
    type: file
    path: backend/src/katalon/core/media_validation.py
  - id: media-storage
    type: file
    path: backend/src/katalon/core/media_storage.py
  - id: search-service
    type: file
    path: backend/src/katalon/services/search_service.py
  - id: export-context
    type: file
    path: backend/src/katalon/services/export_context_service.py
  - id: cantaloupe
    type: file
    path: backend/src/katalon/integrations/cantaloupe.py
  - id: admin-field
    type: file
    path: frontend/admin/src/components/FileField.tsx
  - id: admin-lightbox
    type: file
    path: frontend/admin/src/components/AttachmentLightbox.tsx
  - id: portal-attachment-field
    type: file
    path: frontend/portal/src/components/AttachmentField.tsx
  - id: portal-detail-layout
    type: file
    path: frontend/portal/src/components/DetailPageLayout.tsx
  - id: decision
    type: file
    path: .agents/knowledge/decisions/feldtyp-datei-anhaenge.md
---

The `file` field type attaches files to records of seven types: `object`, `entity`, `place`, `occurrence`, `collection`, `storage_location` and `procedure` [@schema-admin]. Files are not media. They have no IIIF pipeline, no primary image and no per-file rights, and they live in their own `attachments` table, not in `media_files` [@decision] [@models]. The rationale and the rejected alternative (a polymorphic `media_files`) are in the decision record [@decision].

## Data Model

The `Attachment` row stores the record type and id (no foreign key, because the target table is polymorphic), the original filename (512 characters), the content-detected MIME type, byte size, the relative `storage_key`, the uploader (`created_by`, set to null when the user is deleted) and the creation time [@models]. Migration `0088` creates the table with an index on `(record_type, record_id)` and one on `created_by` [@migration]. The row has no field name and no path. Where a file sits is read from the record's current metadata, so moving a group entry or restoring a snapshot needs no update to the row [@models].

The metadata value holds `{id, filename, mime_type, size}`. A repeatable field stores a list, and a group sub-field of type `file` works like a top-level one. On save the backend overwrites `filename`, `mime_type` and `size` from the row, whatever the client sent [@attachment-service].

The storage key has the form `attachments/<first two hex digits of id>/<id>--<safe filename>` and reuses the media storage backend, local or S3 [@media-storage] [@attachment-service].

## Save Check

`validate_metadata` calls `check_and_normalize_attachment_refs` for every record write that has a record id [@schema-service]. The check runs over top-level `file` fields and over `file` sub-fields of groups, and returns these errors:

- A value that is referenced on an unsaved record: the file can be uploaded only after the record exists.
- An id whose row is missing or belongs to another `(record_type, record_id)`: "Datei gehört nicht zu diesem Datensatz."

Structurally malformed values, such as a non-list in a repeatable field, go to `_validate_file_values` in the same service. Only after all references pass does the backend rewrite each value to the stored id, filename, MIME type and size [@attachment-service]. This is the trust boundary: a client cannot make a row of a private record appear in a public field by putting its id into a public one.

## Upload

`POST /v1/attachments/{record_type}/{record_id}` takes a multipart field named `file` and needs the `update` permission on the record type [@attachments-api]. The record must exist and must not be soft-deleted [@attachment-service]. The upload streams to a temporary file and stops with 413 as soon as `ATTACHMENT_MAX_UPLOAD_MB` is exceeded, so the file is never fully accepted first [@attachment-service] [@config]. The content is then sniffed. Only image (JPEG, PNG, TIFF, WebP), PDF, audio (MP3, WAV, OGG) and video (MP4, WebM) pass; the response is 415 otherwise. GIF, SVG, HTML, 3D models and Office files are rejected, and the filename extension and the browser's MIME header are not used [@media-validation] [@attachment-service]. A successful upload returns `{id, filename, mime_type, size}` with status 201 and writes only the row and the stored file. The metadata reference is written by the next record save, under the normal optimistic-locking and audit path [@attachment-service].

## Delivery

### Admin

`GET /v1/attachments/{id}/file` requires the `read` permission on the owning record type and a record that is not soft-deleted. A trashed record therefore returns 404 here too [@attachment-service] [@attachments-api].

`GET /v1/attachments/{id}/link` returns `{"url": "/v1/attachments/{id}/stream?exp=…&uid=…&sig=…"}`. The HMAC covers the scope (`attachment`), attachment id, user id and expiry, uses a key derived from `SECRET_KEY`, and is valid for `ATTACHMENT_LINK_TTL_SECONDS = 300` seconds [@attachment-service]. Media files use the same HMAC with scope `media` (see the media workflow), so an attachment link never opens a media file. `GET /v1/attachments/{id}/stream` is mounted without the bearer dependency and accepts only that link. It loads the user again, requires the user to be active and to hold the read permission, and then streams the file [@attachments-api]. The Admin uses the link for video, audio and PDF. Video and audio can seek with Range requests; a PDF in a `blob:` document would inherit the admin page CSP and be blocked. Images go through an authorized blob fetch [@admin-lightbox] [@admin-field].

### Portal

`GET /portal/v1/attachments/{id}/file` runs the public check on every request and is never cached [@portal-public]. It returns 404 when:

- the row or its record is missing, or the record type is internal (`procedure`, `storage_location`; `INTERNAL_ATTACHMENT_RECORD_TYPES`);
- the record is not publicly visible (`ensure_publicly_visible`);
- the id is not in the projected public metadata of the record, which applies field, group and sub-field visibility and the subtype scope [@public-metadata].

Because the id must appear in the current metadata, removing a file from its field makes it unavailable on the Portal at once, even while the bytes still exist [@portal-public].

### Response Headers

All file responses carry `X-Content-Type-Options: nosniff` and the CSP chosen by `file_security_headers()`, shared with media files [@attachment-service] [@media-api]. They also carry the exact stored `Content-Type`, `Content-Disposition: inline` with the filename (RFC 5987 `filename*` for non-ASCII names) and `Accept-Ranges: bytes`. The Admin response uses `Cache-Control: private, no-store`; the Portal response uses `no-store` [@attachment-service] [@portal-public]. The CSP is `default-src 'none'; sandbox` for images, audio and video. PDFs get `default-src 'none'` without `sandbox`, because browser PDF viewers do not render under that directive [@attachment-service]. A single `bytes=` range returns 206. A range outside the file returns 416. Local storage uses Starlette's `FileResponse`; S3 streams the byte range from the bucket [@attachment-service].

The Portal shows a `file` value as a list in `AttachmentList`. The name opens a lightbox, and a download link stays beside it [@portal-attachment-field] [@portal-detail-layout].

## Lifecycle

| Event | Effect on rows and files |
|---|---|
| Field value removed and record saved | Reference gone from metadata; Portal returns 404 at once; file kept until GC so snapshots can restore it |
| Upload without a later save | Row remains without a reference; GC removes it after the age limit |
| Record moved to trash | Nothing changes; Portal is closed by the public check, Admin returns 404 for the attachment |
| Snapshot restored | References return; a file that no longer exists shows as "Datei nicht mehr vorhanden" in the form |
| Record purged (nightly sweep or manual purge; object, entity, place, occurrence, collection, storage location) | `purge_record_attachments` deletes the rows and calls storage delete. A storage failure is logged and the rows are still removed, so the file stays on disk without a row |
| Procedure deleted (`DELETE /v1/procedures/{id}`) | Procedures have no trash; the delete endpoint calls `purge_record_attachments` directly, so rows and files go with the record |
| Field purged or type changed | `purge_field_data` does not touch attachments; GC removes unreferenced files |

Purge uses the same helper for the nightly `purge_soft_deleted` sweep and for `purge_record_now` [@purge-tasks]. Procedures are outside that path: `_PURGEABLE_MODELS` lists no procedure, and the forced procedure delete removes only the row and its relations [@purge-tasks] [@procedures-api]. Schema field purge is not wired to attachment deletion [@schema-service].

## Garbage Collection

`katalon-manage attachments-gc --older-than 7d [--dry-run]` deletes attachment rows and files older than the given age [@cli]. The age accepts `<n>d`, `<n>h` or `0` (no age limit). The default is 7 days. A row is kept if its id occurs in the current metadata of its record (trashed records included) or in any snapshot of that record. Rows whose record does not exist are orphans and are deleted. Each storage delete happens before its row is removed, and a failed storage delete keeps the row for the next run. The database commit runs once at the end [@attachment-service]. The command is run from cron by the operator; there is no Celery beat job for it [@decision].

Setting `--older-than 0` also removes recent files. It is meant for an attachment that was uploaded by mistake and removed from its field, after any snapshot that still contains it has been deleted [@cli].

## Other Consumers

- Search: `drop_file_values` removes `file` values, top-level and in groups, before indexing. Filenames and reference shape do not reach Elasticsearch in phase 1 [@search-service].
- Export context: `file` fields are excluded from the export field set, so OAI-PMH, LIDO and mapping exports do not emit them [@export-context]. CSV/JSON dumps (`export_service.py`) for callers without read permission use the public projection without `file` fields and return nothing for procedures and storage locations.
- Cantaloupe: the IIIF manifest text skips `file` values [@cantaloupe].
- Not supported in phase 1: vocabulary terms as record type, per-file visibility, licence or rights holder, import and batch editing of file values, and file type restrictions per field [@decision].

## Limits

`ATTACHMENT_MAX_UPLOAD_MB` defaults to 200 in `Settings` and in the Compose files [@config]. The admin file field reads the effective value from `GET /v1/attachments/limits` for its hint and client-side pre-check [@attachments-api]. The outer nginx accepts 500 MB request bodies in `docker/nginx.conf` and `nginx.prod.conf`; `docker/nginx.admin.conf` accepts 200 MB but serves only the direct Admin debugging path. A value above the outer nginx limit cannot be used through the normal path.


The outer nginx adds the page CSP (`object-src 'none'`) at server level. For attachment files (`/(portal/)v1/attachments/{id}/(file|stream)`) and media files (`/(portal/)v1/objects/{id}/media/{id}/(file|stream)`, `/(portal/)v1/media/{id}/(file|download)`) a single regex location repeats the other security headers but not CSP and nosniff, so the API's per-type CSP is the only one; a second page CSP would block the browser PDF viewer. `backend/tests/test_deployment_config.py` exempts exactly these two headers for that location. The admin lightbox loads PDFs through the signed link for the same reason: a `blob:` document inherits the admin page CSP.