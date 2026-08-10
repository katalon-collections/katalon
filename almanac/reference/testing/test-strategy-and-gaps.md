---
title: "Test Strategy And Gaps"
summary: "Reference for Katalon's backend, frontend, E2E, and CI test coverage surfaces and known gaps."
topics: [reference, testing, backend, frontend, ci]
sources:
  - id: backend-tests
    type: file
    path: backend/tests/
  - id: integration-conftest
    type: file
    path: backend/tests/integration/conftest.py
  - id: e2e-tests
    type: file
    path: e2e/tests/
  - id: e2e-package
    type: file
    path: e2e/package.json
  - id: backend-ci
    type: file
    path: .github/workflows/backend.yml
  - id: e2e-ci
    type: file
    path: .github/workflows/e2e.yml
  - id: admin-package
    type: file
    path: frontend/admin/package.json
  - id: portal-package
    type: file
    path: frontend/portal/package.json
---

Katalon's test surface is strongest around backend services and API contracts, lighter around browser flows, and mostly build-only for the two React applications. Backend CI runs unit tests and integration tests separately, Playwright E2E exists but is manually triggered in GitHub Actions, and the frontend packages expose TypeScript builds while only Admin exposes an ESLint script [@backend-ci] [@e2e-ci] [@admin-package] [@portal-package]. Use this reference with the [Testing And Validation](../../guides/development/testing-and-validation) guide.

## Backend Tests

`backend/tests/` contains unit-style and service/API tests for AI, authority adapters, banners, Cantaloupe integration, cleanup tasks, enqueue behavior, first-run initialization, health, identifier services, importer service, media tasks and uploads, OAI-PMH, optimistic locking, pages, PIDs, rate limiting, relations, schema service, search visibility, security policies, subtypes, users, vocabulary import, XML format, and XML security [@backend-tests].

The integration subset lives under `backend/tests/integration/` and covers auth, objects, procedures, schema container fields, and vocabulary term fields [@backend-tests]. Integration fixtures start a PostGIS testcontainer, run Alembic migrations against it, replace Celery's broker/backend with in-memory settings, reload app/config/database modules per test app, reset SlowAPI's process-global counters, skip Cantaloupe health and Elasticsearch index setup, and provide authenticated `httpx` clients [@integration-conftest]. This keeps test isolation independent of request order and does not require external Cantaloupe or Elasticsearch services.

## Backend CI

`.github/workflows/backend.yml` runs on `push` and `pull_request`, sets `KATALON_SECRETS_KEY`, installs Python 3.12, installs backend dependencies with `python -m pip install -e .[dev]`, then runs two jobs [@backend-ci]:

| Job | Command | Notes |
| --- | --- | --- |
| `unit-tests` | `pytest tests --ignore=tests/integration` | Runs first in `backend/`. |
| `integration-tests` | `pytest tests/integration` | Needs `unit-tests`; provides Redis as a GitHub service. |

The workflow uses `pip`; treat that as the CI contract for this workflow [@backend-ci].

## Frontend Checks

Admin exposes `dev`, `build`, `preview`, and `lint` scripts; `build` runs `tsc && vite build`, and `lint` runs ESLint against `src` TypeScript and TSX files [@admin-package]. Portal exposes `dev`, `build`, and `preview`; its `build` also runs `tsc && vite build`, but there is no package-level `lint` script in `frontend/portal/package.json` [@portal-package].

There is no frontend-specific GitHub Actions workflow in the evidence for this page. The E2E workflow installs Admin dependencies, but it does not install Portal dependencies or run Admin/Portal build scripts directly [@e2e-ci].

## E2E Tests

The Playwright suite has three browser specs: Admin login, object creation, and image upload, plus a helper that logs in with `admin@katalon.dev` and waits for a `katalon_token` in local storage [@e2e-tests]. The image upload spec creates an object through `/v1/objects`, opens its Admin form, uploads a tiny PNG through the file input, and expects the uploaded filename to become visible [@e2e-tests].

`e2e/package.json` exposes `npm run test` as `playwright test` and `npm run test:headed` as the headed Playwright run [@e2e-package].

## E2E CI

`.github/workflows/e2e.yml` is configured for `workflow_dispatch`, with push triggers commented out [@e2e-ci]. It starts PostGIS and Redis services, installs Python 3.12 and Node 20, installs backend, Admin, and E2E dependencies, installs Chromium with Playwright, runs `npm run test` from `e2e/`, and uploads the Playwright report artifact for seven days [@e2e-ci].

The E2E environment sets `DATABASE_URL`, `REDIS_URL`, `MEDIA_ROOT`, and `KATALON_SECRETS_KEY` for the Playwright command [@e2e-ci]. The workflow does not define Cantaloupe or Elasticsearch services, so browser coverage that depends on those external services is not represented by this CI job as written [@e2e-ci].

## Current Gaps

| Area | Gap |
| --- | --- |
| E2E scheduling | Playwright runs only by manual workflow dispatch, not on every push or pull request [@e2e-ci]. |
| Browser breadth | The checked-in browser specs cover Admin login, object creation, and image upload; they do not cover Portal search/facets or IIIF viewer behavior, which are described in [Portal Search And Facets](../../architecture/workflows/portal-search-and-facets) and [Media And IIIF](../../architecture/workflows/media-and-iiif) [@e2e-tests]. |
| Frontend automation | Admin has a lint script and both apps have build scripts, but no CI evidence in this page runs those scripts directly [@admin-package] [@portal-package] [@e2e-ci]. |
| External services in E2E CI | The E2E workflow starts PostGIS and Redis only, so Elasticsearch and Cantaloupe-dependent paths need another validation surface [@e2e-ci]. |
