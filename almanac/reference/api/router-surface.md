---
title: "Router Surface"
summary: "Lookup map for Katalon's authenticated `/v1` routers, anonymous portal read model, public paths, dev-only mock routes, and the OAI-PMH prefix exception."
topics: [reference, api, routers]
sources:
  - id: attachments-api
    type: file
    path: backend/src/katalon/api/v1/attachments.py
  - id: media-api
    type: file
    path: backend/src/katalon/api/v1/media.py
  - id: main
    type: file
    path: backend/src/katalon/main.py
  - id: app
    type: file
    path: backend/src/katalon/main.py
  - id: api-dir
    type: file
    path: backend/src/katalon/api/v1/
  - id: api-keys
    type: file
    path: backend/src/katalon/api/v1/api_keys.py
  - id: portal-public
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
  - id: ark-api
    type: file
    path: backend/src/katalon/api/v1/ark.py
  - id: ark-service
    type: file
    path: backend/src/katalon/services/ark_service.py
  - id: rdf-service
    type: file
    path: backend/src/katalon/services/rdf_service.py
---

Katalon's API router surface is mounted in `backend/src/katalon/main.py`. The working API under `/v1` requires a current user (JWT or API key), except for the authentication routes themselves. The Portal projection is separately mounted at `/portal/v1`: it remains anonymous by default but accepts staff JWTs for internal record, schema, and search projections. OAI-PMH is included with no global prefix so it is served at `/oai`; and the DNB URN mock router is included only when `settings.debug` is true [@app] [@api-dir] [@portal-public]. This page is a lookup map for prefixes and exceptions; startup behavior around these mounts is covered by [API Application Startup](../../architecture/backend/api-application-startup).

## Application-Level Paths

| Path | Surface | Notes |
| --- | --- | --- |
| `/api/docs` | Swagger UI | Configured as FastAPI `docs_url` [@app]. |
| `/api/redoc` | ReDoc UI | Configured as FastAPI `redoc_url` [@app]. |
| `/api/openapi.json` | OpenAPI schema | Configured as FastAPI `openapi_url` [@app]. |
| `/health` | Readiness | Checks database, Elasticsearch, Redis, Celery Beat/Worker heartbeat, Cantaloupe, and optional Oxigraph; anonymous callers get only `status`, authenticated callers (JWT or API key) get `checks`, `queue_backlog`, and `backup_age_hours`; the latter two do not gate the status code [@app]. |

## `/v1` Routers

These routers are included with `prefix="/v1"` in `main.py` and a `get_current_user` dependency; only `/v1/auth` is mounted without that dependency. Each router also applies its module-level `APIRouter` prefix unless noted [@app] [@api-dir].

| Effective prefix | Module | Tag or surface |
| --- | --- | --- |
| `/v1/admin/config` | `admin_config.py` | Admin configuration [@api-dir]. |
| `/v1/ai` | `ai.py` | AI suggestions [@api-dir]. |
| `/v1/admin/index-health` | `index_health.py` | Admin search-index health [@api-dir]. |
| `/v1/admin/index-status` | `index_health.py` | Running/queued bulk reindex jobs with progress and ETA [@api-dir]. |
| `/v1/idno` | `idno.py` | Identifier generation [@api-dir]. |
| `/v1/auth` | `auth.py` | Login, HttpOnly refresh-cookie rotation, logout, and password reset [@api-dir]. |
| `/v1/banners` | `banners.py` | Portal banners [@api-dir]. |
| `/v1/users` | `users.py` | User management and current-user endpoints [@api-dir]. |
| `/v1/objects` | `objects.py` | Object records [@api-dir]. |
| `/v1/entities` | `entities.py` | Entity records [@api-dir]. |
| `/v1/places` | `places.py` | Place records [@api-dir]. |
| `/v1/occurrences` | `occurrences.py` | Occurrence records [@api-dir]. |
| `/v1/procedures` | `procedures.py` | Procedure records [@api-dir]. |
| `/v1/collections` | `collections.py` | Collection records and collection hierarchy [@api-dir]. |
| `/v1/storage-locations` | `storage_locations.py` | Internal storage-location records and hierarchy [@api-dir]. |
| `/v1/schema` | `schema_admin.py` | Field definitions [@api-dir]. |
| `/v1/record-subtypes` | `record_subtypes.py` | Record subtype configuration [@api-dir]. |
| `/v1/form-variants` | `form_variants.py` | Form variant configuration (field selection/order per type/subtype, role defaults) [@api-dir]. |
| `/v1/vocabularies` | `vocabularies.py` | Vocabularies and terms [@api-dir]. |
| `/v1/presence` | `presence.py` | Edit-presence heartbeat, release, single-record lookup, and batch lookup for the Admin UI [@api-dir]. |
| `/v1/audit` | `audit.py` | Audit log and snapshots [@api-dir]. |
| `/v1/relations` | `relations.py` | Generic relations [@api-dir]. |
| `/v1/objects/{object_id}/media` | `media.py` main router | Object media files [@api-dir]. |
| `/v1/media` | `media.py` batch router | Batch media import surface [@app] [@api-dir]. |
| `/v1/attachments/{record_type}/{record_id}` | `attachments.py` | Upload of a `file`-field attachment (multipart `file`, `update` permission); writes the row only [@attachments-api]. |
| `/v1/attachments/limits` | `attachments.py` | Configured upload limit (`max_upload_mb` from `ATTACHMENT_MAX_UPLOAD_MB`) for the admin file field hint and pre-check; any logged-in user [@attachments-api]. |
| `/v1/attachments/{attachment_id}/file` | `attachments.py` | Admin file delivery, `read` permission on the owning type [@attachments-api]. |
| `/v1/attachments/{attachment_id}/link` | `attachments.py` | Returns a 300-second signed stream path for `<video>`/`<audio>` [@attachments-api]. |
| `/v1/attachments/{attachment_id}/stream` | `attachments.py` stream router | Streams with the signed link only; mounted without the bearer dependency [@attachments-api] [@main]. |
| `/v1/objects/{object_id}/media/{media_id}/link` | `media.py` main router | Returns a 300-second signed stream path for admin PDF, video and audio [@media-api]. |
| `/v1/objects/{object_id}/media/{media_id}/stream` | `media.py` stream router | Streams with the media signed link only; mounted without the bearer dependency [@media-api] [@main]. |
| `/v1/theme` | `theme.py` | Portal theme manifest [@api-dir]. |
| `/v1/portal` | `portal.py` | Public portal configuration and logo files [@api-dir]. |
| `/v1/pages` | `pages.py` | Static portal pages [@api-dir]. |
| `/v1/search` | `search.py` | Search, facets, and reindex triggers [@api-dir]. |
| `/v1/authorities` | `authority.py` | Authority source lookup [@api-dir]. |
| `/v1/pids` | `pids.py` | Persistent identifier minting: `POST /pids/mint` dispatches to the pid field's configured provider (`dnb_urn` or `ark`); legacy `POST /pids/urn/register` delegates to the same logic [@api-dir]. |
| `/ark:/<NAAN>/<Suffix>` | `ark.py` | Anonymous ARK resolver: redirects a stored public Object, Entity, Place, or Occurrence to its canonical Portal URL [@ark-api] [@ark-service]. |
| `/v1/importer` | `importer.py` | Record import workflows [@api-dir]. |
| `/v1/metadata-mappings` | `metadata_mappings.py` | Import and export mapping configuration [@api-dir]. |
| `/v1/oai-sets` | `oai_sets.py` | OAI-PMH set configuration [@api-dir]. |
| `/sparql` | `sparql.py` | Read-only SPARQL 1.1 Protocol query endpoint (`GET` / `POST`) over the Oxigraph RDF projection, with admin status (`GET /sparql/status`) and rebuild triggers (`POST /sparql/rebuild`); requires authentication by default (`SPARQL_REQUIRE_AUTH`), protected by AST parser read-only guard and query timeouts [@api-dir]. |
Single-record RDF export is an intentional read exception inside otherwise authenticated record routers: the `/v1/{record-family}/{id}/export` handlers use optional authentication, return JSON-LD or Turtle for public records without an API key, and allow authenticated staff to see records their role may read [@api-dir] [@rdf-service]. The admin bulk export router remains authenticated through the global `/v1` dependency and its own admin role dependency [@app] [@api-dir].

Objects, entities, places, occurrences, collections, and storage locations also share admin-only trash routes: `POST /{id}/restore` clears the tombstone, `GET /trash/list` lists soft-deleted rows, and `POST /{id}/purge` permanently deletes one already-trashed row through the same purge path as the scheduled worker. Procedures are excluded from that soft-delete surface [@api-dir].

## `/portal/v1` Read Model

`portal_public.py` is mounted separately at `/portal/v1` with no global authentication dependency. It serves only read paths the React Portal needs: Objects, Entities, Places, Occurrences, their visible relations and object media, the files of public `file` fields (`GET /portal/v1/attachments/{attachment_id}/file`, checked per request against the public projection), quick and advanced portal search, public searchable field definitions, field-scoped vocabulary terms, relation-type vocabulary terms, portal configuration and logo, published pages, active portal banners, and theme data [@app] [@portal-public]. An anonymous request retains the public projection. A valid staff JWT (`superuser`, `admin`, `editor`, `cataloger`, or `viewer`) enables internal records where its backend read permission allows them, all schema fields, and unfiltered inventory search; unrecognised future roles retain anonymous visibility. Advanced search uses `POST /portal/v1/search/advanced`; the body is a validated query description, not a stored or executable Elasticsearch query. `/portal/v1/schema/{type}/fields/{field}/terms` exposes the minimal term projection only when that field is public, searchable, and vocabulary-backed [@portal-public].

Procedures have no `/portal/v1` route. Relation results require both endpoints to be visible inventory records, so a relation to a Procedure is not exposed [@portal-public]. Portal response models are explicit projections rather than shared ORM/API schemas; they omit internal fields such as record versions and search vectors, and relation projections omit relation metadata [@portal-public].

The authenticated `/v1` representations provide navigational `_links`: records link to themselves and relations (Objects additionally link to media); vocabularies link to themselves, terms, and trees; vocabulary terms link to themselves, their vocabulary, ancestors, and where applicable their parent; media link to their Object, file, and — when present — license URI [@api-dir]. The public Portal projections provide the same relative `_links` under `/portal/v1`, pointing at the anonymous read-model endpoints rather than the authenticated `/v1` paths [@portal-public].

The ARK resolver is separate from `/portal/v1`. It stays reachable even when ARK minting is disabled, only accepts the configured production NAAN, rejects the reserved test NAAN `99999`, and looks up public inventory records (including previously public records that are soft-deleted or unpublished, ordered with active rows first); Procedures and never-published drafts are excluded [@ark-api] [@ark-service]. Redirecting withdrawn public ARKs to the canonical portal detail URL lets human visitors land on the portal's HTTP `410 Gone` notice page while RDF clients and SEO crawlers receive `410 Gone` directly [@ark-api] [@ark-service] [@portal-public].

## API Key Routes

`api_keys.py` has no module-level prefix; its route decorators define full paths below the global `/v1` mount [@api-keys] [@app].

| Effective path | Method family | Purpose |
| --- | --- | --- |
| `/v1/users/me/api-keys` | `GET`, `POST` | List or create API keys for the current user [@api-keys]. |
| `/v1/users/me/api-keys/{key_id}` | `DELETE` | Revoke one current-user key [@api-keys]. |
| `/v1/users/{user_id}/api-keys` | `GET`, `POST` | Admin list or create keys for a user [@api-keys]. |
| `/v1/users/{user_id}/api-keys/{key_id}` | `DELETE` | Admin revoke a user's key [@api-keys]. |

## Prefix Exceptions

`oai.py` defines an `APIRouter(prefix="/oai", tags=["oai-pmh"])`, and `main.py` includes it with `prefix=""`, so OAI-PMH lives at `/oai` rather than `/v1/oai` [@api-dir] [@app]. The workflow using that public OAI surface is described in [OAI And Export Mappings](../../architecture/workflows/oai-and-export-mappings).

`dnb_urn_mock.py` defines `/dnb-urn-mock` routes, but `main.py` includes that router under `/v1` only when `settings.debug` is true [@api-dir] [@app]. Treat `/v1/dnb-urn-mock` as a development and test fixture, not as a production API surface.
