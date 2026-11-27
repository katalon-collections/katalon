---
title: "API Application Startup"
summary: "Katalon's FastAPI app initializes security checks, default database rows, Cantaloupe readiness, router mounting, rate limiting, CORS, and health endpoints during import and lifespan startup."
topics: [architecture, api, startup, operations]
sources:
  - id: app
    type: file
    path: backend/src/katalon/main.py
  - id: container-bootstrap
    type: file
    path: backend/src/katalon/management/bootstrap.py
  - id: entrypoint
    type: file
    path: backend/docker-entrypoint.sh
  - id: worker-start-test
    type: file
    path: backend/tests/integration/test_api_workers.py
  - id: config
    type: file
    path: backend/src/katalon/config.py
  - id: main-tests
    type: file
    path: backend/tests/test_main.py
  - id: health-tests
    type: file
    path: backend/tests/test_health.py
  - id: health-tasks
    type: file
    path: backend/src/katalon/workers/health_tasks.py
  - id: openapi-generator
    type: file
    path: scripts/gen_openapi.py
---

Katalon's API starts from `backend/src/katalon/main.py`, where FastAPI is configured with OpenAPI metadata, SlowAPI rate limiting, CORS, router mounts, a lifespan startup routine, and the `/health` readiness endpoint [@app]. Startup refuses insecure production secrets, ensures required default rows exist, verifies Cantaloupe, and attempts to create the Elasticsearch index [@app]. In the API container these shared steps run once in the entrypoint before Uvicorn spawns workers [@entrypoint] [@container-bootstrap]. Settings come from Pydantic `BaseSettings`, so environment variables and `.env` values drive service URLs, secrets, token lifetimes, media paths, CORS, and feature settings [@config].

## Lifespan Sequence

`initialize_application()` checks production secrets and media-directory access, then ensures the first admin account, media and relation type vocabularies, Portal/Admin singleton configuration, authority sources, generic label/idno fields, and the collection description field. It verifies Cantaloupe and attempts Elasticsearch initialization; an Elasticsearch failure is logged and does not stop startup [@app]. Record subtype defaults are maintained by migrations, rather than another lifespan seed step.

After migrations, the API entrypoint invokes `python -m katalon.management.bootstrap` before executing a `uvicorn` command. Only successful initialization sets the internal `KATALON_BOOTSTRAPPED=1` marker inherited by its workers. The bootstrap process closes its Elasticsearch client and database engine before exiting [@entrypoint] [@container-bootstrap]. Each worker still validates production secrets and media access, but skips shared seeding when the marker is present. This avoids duplicate default rows and prevents a second worker from deleting the first worker's newly written credentials file. Direct host startup without that marker keeps the original lifespan initialization path; use a single host worker, or the container entrypoint for multiple workers [@app].

The integration regression starts the actual entrypoint against an isolated migrated database, supplies a test Cantaloupe server, waits for two distinct Uvicorn worker processes to become ready, requests the OpenAPI endpoint, and verifies that the first-run credentials file remains available [@worker-start-test]. This covers one API container. Simultaneous independent API containers and concurrent migrations require separate coordination.

## Application Object

The FastAPI object uses package metadata for its version when the `katalon` package is installed, falling back to `0.0.0-dev` when package metadata is absent [@app]. API documentation is exposed at `/api/docs`, `/api/redoc`, and `/api/openapi.json`. Operation IDs combine tag, handler, method, and route path so they remain unique and stable for generated clients. `scripts/gen_openapi.py` validates `app.openapi()` against FastAPI's OpenAPI model, writes the repository's static `openapi.json`, and supports a CI check that fails when the static copy is stale [@app] [@openapi-generator].

`docs_url`/`redoc_url` are set to `None` on the `FastAPI(...)` constructor; `/api/docs` and `/api/redoc` are hand-rolled routes instead, serving Swagger UI / ReDoc assets vendored under `src/katalon/static/docs/` (mounted at `/api/docs-static/`) rather than FastAPI's CDN defaults [@app]. This is required, not cosmetic: nginx's CSP sets `script-src 'self'` with no CDN or `'unsafe-inline'` exception (`docker/nginx*.conf`), so FastAPI's built-in `get_swagger_ui_html()` — which always emits an inline `<script>` init block — cannot be used for Swagger UI; the custom route emits pure `<script src="...">` tags instead, with the init call in `static/docs/swagger-ui-init.js`. ReDoc has no such inline block, so `get_redoc_html()` is reused directly, just pointed at the local JS bundle with `with_google_fonts=False` (Google Fonts is also blocked by the same CSP). See `src/katalon/static/docs/VENDORED.md` for the vendored versions and how to update them.

The router list is broad: admin config, AI, index health, id number generation, auth, users, records, schema, vocabularies, audit, relations, media, theme, portal, pages, search, authorities, persistent identifiers, importer, metadata mappings, OAI sets, and API keys are mounted under `/v1` [@app]. OAI-PMH routes are mounted with an empty prefix, and the DNB URN mock router is mounted only when `settings.debug` is true [@app].

## CORS, Rate Limits, And Health

The API attaches a SlowAPI limiter to `app.state`, installs the rate-limit exception handler, and configures CORS from `settings.cors_origins` [@app]. Default CORS origins cover local Admin and Portal development ports plus Vite's default localhost addresses [@config].

The `/health` endpoint checks database access with `SELECT 1`, Elasticsearch with `ping()`, Redis reachability, the default Celery queue backlog, a Beat/Worker heartbeat key, Cantaloupe's IIIF Image API root, and Oxigraph only when it is enabled [@app]. The heartbeat task is enqueued by Celery Beat every two minutes and refreshed by a worker with a ten-minute TTL; a missing key deliberately treats Beat, worker, or Redis failure as the same degraded background-processing outage [@health-tasks]. The endpoint returns status `ok` with HTTP 200 only when every entry in `checks` is `ok`; otherwise it returns status `degraded` with HTTP 503. `queue_backlog` and `backup_age_hours` are informational and do not affect the status code [@app]. Tests assert the default check set, the informational fields, status-code consistency, unique OpenAPI operation IDs, and the `Katalon API` schema title [@health-tests]. Anonymous callers receive only `status` with the HTTP status code; authenticated callers receive the per-service details, and a failing authentication lookup falls back to the anonymous answer.

## Enforced Startup Contracts

Tests cover two startup-adjacent contracts. `Settings` requires a valid `katalon_secrets_key`, and `_check_production_secrets()` accepts production mode only when `SECRET_KEY` is strong and `INITIAL_ADMIN_PASSWORD` is not a known default when `KATALON_BASE_URL` is empty [@main-tests]. These tests make the security startup checks part of the verified API behavior, not just local convention.

## Related Pages

This startup path sits inside the [System Overview](../system/system-overview), shares its security boundary with [Security And Configuration](security-and-configuration), and inherits its health-check policy from [Deep Health Check](../../decisions/operations/deep-health-check). For the mounted endpoint families, use [Router Surface](../../reference/api/router-surface).
