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
  - id: e2e-config
    type: file
    path: e2e/playwright.config.ts
  - id: e2e-package
    type: file
    path: e2e/package.json
  - id: portal-a11y-spec
    type: file
    path: e2e/tests/portal-a11y.spec.ts
  - id: portal-app
    type: file
    path: frontend/portal/src/App.tsx
  - id: backend-ci
    type: file
    path: .github/workflows/backend.yml
  - id: e2e-ci
    type: file
    path: .github/workflows/e2e.yml
  - id: dependabot
    type: file
    path: .github/dependabot.yml
  - id: admin-package
    type: file
    path: frontend/admin/package.json
  - id: portal-package
    type: file
    path: frontend/portal/package.json
---

Katalon's test surface is strongest around backend services and API contracts, lighter around browser flows, and mostly build-only for the two React applications. Backend CI runs unit tests and integration tests separately, Playwright E2E exists but is manually triggered in GitHub Actions, and the frontend packages expose TypeScript builds while only Admin exposes an ESLint script [@backend-ci] [@e2e-ci] [@admin-package] [@portal-package]. The checked-in workflows pin third-party actions to full commit SHAs and use Dependabot's `github-actions` ecosystem for weekly update PRs [@backend-ci] [@e2e-ci] [@dependabot]. Portal accessibility now has a small automated axe surface for the home page and search results page, but the wider accessibility audit is still not represented by this suite [@portal-a11y-spec]. Use this reference with the [Testing And Validation](../../guides/development/testing-and-validation) guide.

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

The backend workflow pins `actions/checkout` and `actions/setup-python` by 40-character commit SHA with version comments, rather than mutable major-version tags [@backend-ci].

## Frontend Checks

Admin exposes `dev`, `build`, `preview`, and `lint` scripts; `build` runs `tsc && vite build`, and `lint` runs ESLint against `src` TypeScript and TSX files [@admin-package]. Portal exposes `dev`, `build`, and `preview`; its `build` also runs `tsc && vite build`, but there is no package-level `lint` script in `frontend/portal/package.json` [@portal-package].

There is no frontend-specific GitHub Actions workflow in the evidence for this page. The Playwright config starts both Vite dev servers, but the E2E workflow installs Admin and E2E dependencies only; it neither installs Portal dependencies nor runs Admin or Portal build scripts directly [@e2e-ci] [@e2e-config].

## E2E Tests

The Playwright suite has browser specs for Admin login, object creation, image upload, Admin responsive layout, relation quick creation, Portal search, and Portal axe checks. The Admin helper logs in with `admin@katalon.dev` and waits for a `katalon_token` in local storage [@e2e-tests]. The image upload spec creates an object through `/v1/objects`, opens its Admin form, uploads a tiny PNG through the file input, and expects the uploaded filename to become visible [@e2e-tests]. The responsive spec checks narrow object lists, configuration screens, schema subtype controls, and form grids against horizontal overflow and touch-target expectations [@e2e-tests]. The relation quick-create spec covers generic relation picker draft creation, focus recovery, touch targets, and relation-field quick-create options across primary types [@e2e-tests]. The Portal search spec mocks portal config and search responses to cover configured facets, disabled built-in facets, multi-value metadata filters, translated field-label fallback, and refinement that preserves active filters [@e2e-tests].

`portal-a11y.spec.ts` uses `@axe-core/playwright` with `wcag2a` and `wcag2aa` tags against the Portal home page and mocked search results page [@portal-a11y-spec] [@e2e-package]. The Portal header search input is a real control covered by that surface: it uses `role="combobox"` with `aria-autocomplete="list"`, `aria-expanded`, and `aria-controls`, so ARIA state attributes are attached to an allowed role [@portal-app].

`e2e/package.json` exposes `npm run test` as `playwright test` and `npm run test:headed` as the headed Playwright run [@e2e-package].

## E2E CI

`.github/workflows/e2e.yml` is configured for `workflow_dispatch`, with push triggers commented out [@e2e-ci]. It starts PostGIS, Redis, and Cantaloupe services, installs Python 3.12 and Node 20, installs backend, Admin, and E2E dependencies, installs Chromium with Playwright, runs `npm run test` from `e2e/`, and uploads the Playwright report artifact for seven days [@e2e-ci].

The E2E environment sets `DATABASE_URL`, `REDIS_URL`, `CANTALOUPE_URL`, `MEDIA_ROOT`, and `KATALON_SECRETS_KEY` for the Playwright command [@e2e-ci]. The workflow does not define an Elasticsearch service, so search paths that need Elasticsearch are not represented by this CI job as written [@e2e-ci].

## Current Gaps

| Area | Gap |
| --- | --- |
| E2E scheduling | Playwright runs only by manual workflow dispatch, not on every push or pull request [@e2e-ci]. |
| Browser breadth | The checked-in browser specs cover Admin login, object creation, image upload, responsive Admin layout, relation quick creation, mocked Portal search/facet behavior, and axe checks for Portal home/search pages; they do not cover IIIF viewer behavior, Portal detail-page accessibility, Admin axe checks, or Portal search against a live Elasticsearch service, which are described in [Media And IIIF](../../architecture/workflows/media-and-iiif) and [Portal Search And Facets](../../architecture/workflows/portal-search-and-facets) [@e2e-tests] [@portal-a11y-spec]. |
| Frontend automation | Admin has a lint script and both apps have build scripts, but no CI evidence in this page runs those scripts directly; the E2E workflow also does not install Portal dependencies although Playwright starts the Portal dev server [@admin-package] [@portal-package] [@e2e-ci] [@e2e-config]. |
| External services in E2E CI | The E2E workflow starts PostGIS, Redis, and Cantaloupe, but not Elasticsearch, so Elasticsearch-dependent search paths need another validation surface [@e2e-ci]. |
