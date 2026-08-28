---
title: "Environment And Secrets"
summary: "Reference for Katalon environment variables, startup secret gates, first-run credentials, and test-only secret requirements."
topics: [reference, operations, configuration, security, testing]
sources:
  - id: env-example
    type: file
    path: .env.example
  - id: config
    type: file
    path: backend/src/katalon/config.py
  - id: errors
    type: file
    path: backend/src/katalon/errors.py
  - id: management-runner
    type: file
    path: backend/src/katalon/management/runner.py
  - id: main
    type: file
    path: backend/src/katalon/main.py
  - id: compose
    type: file
    path: docker-compose.yml
  - id: dev-compose
    type: file
    path: docker-compose.dev.yml
  - id: security-tests
    type: file
    path: backend/tests/test_security_policies.py
  - id: pytest-gotcha
    type: file
    path: .agents/knowledge/gotchas/pytest-secrets-key.md
---

Katalon reads backend configuration through Pydantic settings, with `.env` support and environment variables mapped to fields in `backend/src/katalon/config.py` [@config]. `.env` files are resolved relative to the source tree, not the current working directory: a source checkout reads `backend/.env` and then the repository root `.env`; the flatter Docker layout reads `/app/.env` and otherwise uses the environment supplied by Compose [@config] [@compose] [@dev-compose]. Most variables have development defaults, but `KATALON_SECRETS_KEY` is required at settings construction time and must be at least 32 characters [@config]. On the CLI, a missing or too-short `KATALON_SECRETS_KEY` surfaces as a single readable message through the `katalon-manage` launcher rather than a Pydantic stack trace [@errors] [@management-runner]. Production startup also refuses insecure `SECRET_KEY` values and well-known default admin passwords when `DEBUG` is false [@main].

## Required Secrets

| Variable | Required by | Rule |
|---|---|---|
| `KATALON_SECRETS_KEY` | Settings construction, Compose API and worker services | No default; minimum length 32 [@config] [@compose] |
| `SECRET_KEY` | JWT and app security settings | Must not be a default value and must be at least 32 characters when `DEBUG=false` [@config] [@main] |
| `POSTGRES_PASSWORD` | PostgreSQL, backup, and database URL construction | Provided by `.env`; no safe production default in `.env.example` [@env-example] [@compose] |
| `DATABASE_URL` | API and worker database connection | Passed explicitly into API and worker services [@compose] |

`.env.example` marks `SECRET_KEY` and `KATALON_SECRETS_KEY` as values to change and recommends generating at least 32 random characters for `SECRET_KEY` [@env-example].

## Startup Secret Gates

When `settings.debug` is false, `_check_production_secrets` raises `RuntimeError` if `SECRET_KEY` is one of the known defaults or shorter than 32 characters. The same gate rejects `DEFAULT_ADMIN_PASSWORD` values of `admin`, `password`, or `katalon` [@main].

The DNB URN mock router is only registered when `settings.debug` is true, so its writable in-memory test endpoints are not exposed in production mode [@main].

## First-Run Admin Variables

| Variable | Default | Effect |
|---|---|---|
| `KATALON_BASE_URL` | empty string | If present, startup derives `admin@<host>` from the URL and creates a `superuser` with a random first-run password [@main] |
| `DEFAULT_ADMIN_EMAIL` | `admin@katalon.dev` in settings, `admin@example.org` in example env | Used when no admin or superuser exists and no email can be derived from `KATALON_BASE_URL` [@config] [@env-example] [@main] |
| `DEFAULT_ADMIN_PASSWORD` | `admin` in settings, placeholder in example env | Used only for first admin creation when `KATALON_BASE_URL` is empty [@config] [@main] |
| `FIRST_RUN_CREDENTIALS_PATH` | `/var/lib/katalon/first-run-credentials.txt` | File path for random first-run credentials when `KATALON_BASE_URL` is used [@config] [@main] |

On first startup with no existing admin or superuser and a usable `KATALON_BASE_URL`, Katalon writes the derived email and random password to `FIRST_RUN_CREDENTIALS_PATH` with file mode `0600` and also logs the first-run block [@main]. Without `KATALON_BASE_URL`, it creates an `admin` role user from `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` and logs that it is falling back to configured default credentials [@main].

## Service And Integration Variables

| Variable | Default in settings or Compose | Main use |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` in settings, `redis://redis:6379/0` in Compose | Celery and Redis-backed services [@config] [@compose] |
| `ELASTICSEARCH_URL` | `http://localhost:9200` in settings, `http://elasticsearch:9200` in Compose | Search indexing and health checks [@config] [@compose] |
| `ES_INDEX_NAME` | `katalon_records` | Elasticsearch record index name [@config] [@env-example] |
| `CANTALOUPE_URL` | `http://localhost:8182` in settings, `http://cantaloupe:8182` in Compose | Internal IIIF image server URL [@config] [@compose] |
| `CANTALOUPE_PUBLIC_URL` | `http://localhost` locally; instance URL in production | Public IIIF base used in manifests. It must be browser-reachable and must not use the internal Cantaloupe port [@config] [@compose] |
| `MEDIA_ROOT` | `/var/lib/katalon/media` in settings and containers | Media storage path inside containers; host path is mounted from env [@config] [@compose] |
| `MAX_UPLOAD_SIZE_MB` | `100` in settings, `200` in Compose and example env | Upload size limit [@config] [@compose] [@env-example] |
| `OAI_ADMIN_EMAIL` | `admin@katalon.dev` | OAI-PMH admin email setting [@config] |
| `GEONAMES_USERNAME` | `demo` | GeoNames webservice account name, passed through to the Compose API service [@config] [@compose] [@env-example] |
| `WIKIDATA_USER_AGENT` | empty | Optional authority lookup user agent; `.env.example` says to leave it empty to derive from base URL and admin email [@env-example] [@config] |
| `DNB_URN_*` | disabled and empty credentials by default | DNB URN integration settings [@config] [@env-example] |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | empty | Optional Telegram feedback or notification settings passed into API service [@config] [@compose] |
| `AI_REQUEST_TIMEOUT_SECONDS` | `60` | Timeout setting for AI requests [@config] |

API startup checks Cantaloupe by requesting `<CANTALOUPE_URL>/iiif/3` and refuses to start if the image server is unreachable or returns an error response [@main].

## CORS And Debug

`CORS_ORIGINS` is a list setting. The built-in default allows localhost Admin and Portal development origins on `3000`, `3001`, `5173`, and `127.0.0.1:5173`; `.env.example` shows a production JSON array without trailing slashes [@config] [@env-example]. `DEBUG` defaults to `false` in settings and `.env.example`, and Compose passes `DEBUG` to the API with a default of `false` [@config] [@env-example] [@compose].

The dev-compose override leaves `KATALON_SECRETS_KEY` as an environment-supplied value for the API and worker, so the dev stack still needs that secret even though it changes images, mounts source directories, and enables reload-oriented commands [@dev-compose].

## Test-Only Secret Requirement

Because `Settings()` is instantiated during imports, backend tests that import the application require `KATALON_SECRETS_KEY` before collection can complete [@config] [@pytest-gotcha]. The project gotcha records the known failure mode as Pydantic validation errors during pytest collection and uses this minimal command shape:

```bash
cd backend
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run pytest -q
```

Because `Settings` now also resolves the repository root `.env` regardless of the working directory, running from the repo root can satisfy the requirement from `.env` without exporting the variable manually. The explicit env-var form above stays the documented, environment-agnostic default [@config].

The security policy tests import `app` from `katalon.main`, so they depend on settings import succeeding before the actual route assertions can run [@security-tests]. Broader test commands and validation context belong in [Testing And Validation](../../guides/development/testing-and-validation), while the backend configuration architecture is covered by [Security And Configuration](../../architecture/backend/security-and-configuration).
