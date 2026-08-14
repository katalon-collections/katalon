---
title: "API Application Startup"
summary: "Katalon's FastAPI app initializes security checks, default database rows, Cantaloupe readiness, router mounting, rate limiting, CORS, and health endpoints during import and lifespan startup."
topics: [architecture, api, startup, operations]
sources:
  - id: app
    type: file
    path: backend/src/katalon/main.py
  - id: config
    type: file
    path: backend/src/katalon/config.py
  - id: main-tests
    type: file
    path: backend/tests/test_main.py
  - id: health-tests
    type: file
    path: backend/tests/test_health.py
---

Katalon's API starts from `backend/src/katalon/main.py`, where FastAPI is configured with OpenAPI metadata, SlowAPI rate limiting, CORS, router mounts, a lifespan startup routine, and the `/health` readiness endpoint [@app]. Startup is not passive: the lifespan function refuses insecure production secrets, ensures required default rows exist, verifies Cantaloupe, and attempts to create the Elasticsearch index [@app]. Settings come from Pydantic `BaseSettings`, so environment variables and `.env` values drive service URLs, secrets, token lifetimes, media paths, CORS, and feature settings [@config].

## Lifespan Sequence

The lifespan function runs `_check_production_secrets()` first, then ensures the first admin account, media type vocabulary, relation type vocabulary, record subtypes, portal config, admin config, authority sources, default label fields, and Cantaloupe health [@app]. Only after those required steps does it try `ensure_index()` for Elasticsearch, and that call is wrapped in a broad `except` so Elasticsearch initialization failure does not stop startup [@app].

The seed functions are intentionally narrow. They create missing defaults such as `media_types`, `relation_types`, default record subtypes, singleton config rows, authority sources, and a required `label` field for every primary type including procedures [@app]. They do not recreate existing rows, which keeps startup idempotent.

## Application Object

The FastAPI object uses package metadata for its version when the `katalon` package is installed, falling back to `0.0.0-dev` when package metadata is absent [@app]. API documentation is exposed at `/api/docs`, `/api/redoc`, and `/api/openapi.json`, while most business routers are included under `/v1` [@app].

The router list is broad: admin config, AI, index health, id number generation, auth, users, records, schema, vocabularies, audit, relations, media, theme, portal, pages, search, authorities, persistent identifiers, importer, metadata mappings, OAI sets, feedback, and API keys are mounted under `/v1` [@app]. OAI-PMH routes are mounted with an empty prefix, and the DNB URN mock router is mounted only when `settings.debug` is true [@app].

## CORS, Rate Limits, And Health

The API attaches a SlowAPI limiter to `app.state`, installs the rate-limit exception handler, and configures CORS from `settings.cors_origins` [@app]. Default CORS origins cover local Admin and Portal development ports plus Vite's default localhost addresses [@config].

The `/health` endpoint checks database access with `SELECT 1` and Elasticsearch with `ping()`, then returns status `ok` with HTTP 200 only when both checks are `ok`; otherwise it returns status `degraded` with HTTP 503 [@app]. Tests assert that the health response always reports exactly `database` and `elasticsearch` checks, that status and status code match check results, and that `/api/openapi.json` exposes the `Katalon API` title [@health-tests].

## Enforced Startup Contracts

Tests cover two startup-adjacent contracts. `Settings` requires a valid `katalon_secrets_key`, and `_check_production_secrets()` accepts production mode only when `SECRET_KEY` is strong and `DEFAULT_ADMIN_PASSWORD` is not a known default [@main-tests]. These tests make the security startup checks part of the verified API behavior, not just local convention.

## Related Pages

This startup path sits inside the [System Overview](../system/system-overview), shares its security boundary with [Security And Configuration](security-and-configuration), and inherits its health-check policy from [Deep Health Check](../../decisions/operations/deep-health-check). For the mounted endpoint families, use [Router Surface](../../reference/api/router-surface).
