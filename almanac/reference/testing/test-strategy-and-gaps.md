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
  - id: security-ci
    type: file
    path: .github/workflows/security.yml
  - id: load-smoke-ci
    type: file
    path: .github/workflows/load-smoke.yml
  - id: dast-ci
    type: file
    path: .github/workflows/dast-staging.yml
  - id: backup-drill-ci
    type: file
    path: .github/workflows/backup-drill.yml
  - id: e2e-ci
    type: file
    path: .github/workflows/e2e.yml
  - id: dependabot
    type: file
    path: .github/dependabot.yml
  - id: backend-pyproject
    type: file
    path: backend/pyproject.toml
  - id: performance-readme
    type: file
    path: backend/tests/performance/README.md
  - id: performance-locust
    type: file
    path: backend/tests/performance/locustfile.py
  - id: route-security-boundaries
    type: file
    path: backend/tests/test_route_security_boundaries.py
  - id: import-resilience-tests
    type: file
    path: backend/tests/integration/test_import_resilience.py
  - id: schema-destructive-tests
    type: file
    path: backend/tests/integration/test_schema_destructive_changes.py
  - id: backup-drill-test
    type: file
    path: backend/tests/integration/test_backup_restore_drill.py
  - id: frontend-ci
    type: file
    path: .github/workflows/frontend.yml
  - id: admin-test-config
    type: file
    path: frontend/admin/vitest.config.ts
  - id: admin-test-setup
    type: file
    path: frontend/admin/src/setupTests.ts
  - id: portal-test-config
    type: file
    path: frontend/portal/vite.config.ts
  - id: admin-package
    type: file
    path: frontend/admin/package.json
  - id: portal-package
    type: file
    path: frontend/portal/package.json
---

Katalon's test surface is strongest around backend services, API contracts, and structural data-safety checks, lighter around browser flows, with Vitest unit and component tests for both React applications. Backend CI runs unit tests and integration tests separately, security CI runs source/dependency/secret checks on push and pull request, Playwright E2E is manually triggered, and scheduled workflows cover staging DAST, staging load smoke, and an automated restore drill [@backend-ci] [@security-ci] [@e2e-ci] [@dast-ci] [@load-smoke-ci] [@backup-drill-ci]. The frontend packages expose TypeScript builds while only Admin exposes an ESLint script [@admin-package] [@portal-package]. The checked-in workflows pin most third-party actions to full commit SHAs and use Dependabot's `github-actions` ecosystem for weekly update PRs [@backend-ci] [@security-ci] [@e2e-ci] [@dependabot]. Portal accessibility now has a small automated axe surface for the home page and search results page, but the wider accessibility audit is still not represented by this suite [@portal-a11y-spec]. Use this reference with the [Testing And Validation](../../guides/development/testing-and-validation) guide.

## Backend Tests

`backend/tests/` contains unit-style and service/API tests for AI, authority adapters, banners, Cantaloupe integration, cleanup tasks, enqueue behavior, first-run initialization, health, identifier services, importer service, media tasks and uploads, OAI-PMH, optimistic locking, pages, PIDs, rate limiting, relations, schema service, search visibility, security policies, structural route-security boundaries, subtypes, users, vocabulary import, XML format, and XML security [@backend-tests] [@route-security-boundaries].

The integration subset lives under `backend/tests/integration/` and covers auth, objects, procedures, schema container fields, vocabulary term fields, import rollback behavior, destructive schema-change data retention, and the scheduled backup/restore drill [@backend-tests] [@import-resilience-tests] [@schema-destructive-tests] [@backup-drill-test]. Integration fixtures start a PostGIS testcontainer, run Alembic migrations against it, replace Celery's broker/backend with in-memory settings, reload app/config/database modules per test app, reset SlowAPI's process-global counters, skip Cantaloupe health and Elasticsearch index setup, and provide authenticated `httpx` clients [@integration-conftest]. This keeps test isolation independent of request order and does not require external Cantaloupe or Elasticsearch services.

`test_route_security_boundaries.py` reads FastAPI's generated OpenAPI schema and asserts two route-shape invariants: every `/v1/*` operation must declare a credential requirement except the documented auth bootstrap/reset endpoints, and public `/portal/v1/*` operations must stay read-only except the advanced-search POST [@route-security-boundaries]. These checks complement role-specific security-policy tests because they fail when a future route is mounted outside the expected auth boundary [@route-security-boundaries].

The import resilience tests patch `AsyncSession.flush()` to raise during `import_records_task.run()` and then assert no partial Objects survive, locking down the import task's single-final-commit behavior [@import-resilience-tests]. The destructive schema tests assert that deleting a field soft-hides it from active schema reads without deleting existing object metadata, and that deleting a vocabulary term does not delete or rewrite records that store a denormalized term snapshot in JSONB metadata [@schema-destructive-tests]. `test_after_commit_rollback.py` tests that database rollbacks (in both HTTP request lifecycles and direct session generator blocks) discard all `after_commit` hooks, ensuring zero Celery task dispatches, zero Elasticsearch documents, zero RDF projections, and zero cleanup runs, while successful commits dispatch to consuming worker doubles that process committed data with verified database visibility (#392).

## Backend CI

`.github/workflows/backend.yml` runs on `push` and `pull_request`, sets `KATALON_SECRETS_KEY`, installs Python 3.14, installs backend dependencies with `python -m pip install -e .[dev]`, then runs two jobs [@backend-ci]:

| Job | Command | Notes |
| --- | --- | --- |
| `unit-tests` | `pytest tests --ignore=tests/integration` | Runs first in `backend/`. |
| `integration-tests` | `pytest tests/integration -m "not backup_drill"` | Needs `unit-tests`; provides Redis as a GitHub service; excludes the scheduled restore drill. |

The workflow uses `pip`; treat that as the CI contract for this workflow [@backend-ci].

The backend workflow pins `actions/checkout` and `actions/setup-python` by 40-character commit SHA with version comments, rather than mutable major-version tags [@backend-ci].

## Security CI

`.github/workflows/security.yml` runs on `push` and `pull_request` and contains four independent jobs: Ruff linting with flake8-bandit security rules, `pip-audit` for backend dependency CVEs, `pnpm audit --audit-level=high` for both frontend packages, and Gitleaks secret scanning over full checkout history [@security-ci]. The Ruff rule set includes `S` and `backend/pyproject.toml` gives tests and selected scripts per-file ignores, so the workflow is a static source check rather than a separate Bandit command [@security-ci] [@backend-pyproject].

## Performance And Load Checks

Katalon uses Locust, not k6, for checked-in load testing; `locust` is a backend dev dependency and `backend/tests/performance/README.md` documents local, production-URL, public-only, and headless runs [@backend-pyproject] [@performance-readme]. The locustfile defines `PublicPortalUser` with weight 4 and `AdminUser` with weight 1, so the default workload is mostly unauthenticated portal traffic with a smaller authenticated admin/cataloguing share [@performance-locust]. `KATALON_LOCUST_PROFILE` selects the fixed `smoke`, `normal`, or `load` profiles; heavy-load, stress, and soak profiles are intentionally deferred because they need infrastructure rather than another local script [@performance-readme] [@performance-locust].

The Locust run has one CI gate: an `events.quitting` handler compares the total fail ratio to `KATALON_LOCUST_MAX_FAIL_RATIO`, defaulting to 1 percent, and exits non-zero when the threshold is exceeded [@performance-locust]. `.github/workflows/load-smoke.yml` runs the `smoke` profile weekly against `STAGING_URL` with staging credentials and uploads an HTML report; it is schedule/manual only because it hits a real staging instance [@load-smoke-ci].

## DAST And Restore Drills

`.github/workflows/dast-staging.yml` runs OWASP ZAP full scan against the configured staging URL weekly or manually, with issue writing enabled and `fail_action: true`; its own comments define it as an attack-style staging check, not a PR/push gate [@dast-ci].

The automated backup drill is separate from ordinary integration CI. `test_backup_restore_drill.py` seeds a test database with a Collection, Object, and `member_of` relation, runs `pg_dump` from a matching `postgis/postgis:16-3.4` client container, restores the dump into an unrelated Postgres container with `psql`, and asserts the records and relation survived [@backup-drill-test]. The `backup_drill` pytest marker is registered in `backend/pyproject.toml`, excluded from normal backend integration CI, and run quarterly or manually by `.github/workflows/backup-drill.yml` [@backend-pyproject] [@backend-ci] [@backup-drill-ci].

## Frontend Checks

Both apps expose `test` (`vitest run`) and `test:watch` (`vitest`) scripts,
with jsdom and React Testing Library for tests beside the source files.
Admin uses a separate Vitest config merged with its Vite config; Portal
keeps its test settings in Vite. Admin's setup cleans up rendered components
after each test [@admin-package] [@portal-package] [@admin-test-config]
[@portal-test-config] [@admin-test-setup].

Admin examples cover form-variant priority, confirmation actions while
pending, and multilingual input editing. Portal tests cover utilities,
search filter and paging state, and components including the IIIF viewer,
map, and tree facets. These jsdom tests do not prove browser layout or
live-service integration.

`.github/workflows/frontend.yml` runs an Admin/Portal matrix on pushes and
pull requests. Both jobs install frozen lockfiles, run TypeScript checks,
and execute Vitest; Admin also runs ESLint. Both package build scripts
still run `tsc && vite build` separately from this workflow [@frontend-ci]
[@admin-package] [@portal-package].

## E2E Tests

The Playwright config starts the API and both Vite development servers for its browser checks [@e2e-config].

The Playwright suite has browser specs for Admin login, object creation, image upload, Admin responsive layout, relation quick creation, Portal search, and Portal axe checks. The Admin helper logs in with `admin@katalon.dev` and waits for a `katalon_token` in local storage [@e2e-tests]. The image upload spec creates an object through `/v1/objects`, opens its Admin form, uploads a tiny PNG through the file input, and expects the uploaded filename to become visible [@e2e-tests]. The responsive spec checks narrow object lists, configuration screens, schema subtype controls, and form grids against horizontal overflow and touch-target expectations [@e2e-tests]. The relation quick-create spec covers generic relation picker draft creation, focus recovery, touch targets, and relation-field quick-create options across primary types [@e2e-tests]. The Portal search spec mocks portal config and search responses to cover configured facets, disabled built-in facets, multi-value metadata filters, translated field-label fallback, and refinement that preserves active filters [@e2e-tests].

`portal-a11y.spec.ts` uses `@axe-core/playwright` with `wcag2a` and `wcag2aa` tags against the Portal home page and mocked search results page [@portal-a11y-spec] [@e2e-package]. The Portal header search input is a real control covered by that surface: it uses `role="combobox"` with `aria-autocomplete="list"`, `aria-expanded`, and `aria-controls`, so ARIA state attributes are attached to an allowed role [@portal-app].

`e2e/package.json` exposes `pnpm test` as `playwright test` and `pnpm run test:headed` as the headed Playwright run [@e2e-package].

## E2E CI

`.github/workflows/e2e.yml` is configured for `workflow_dispatch`, with push triggers commented out [@e2e-ci]. It starts PostGIS, Redis, and Cantaloupe services, installs Python 3.14, Node 22, and pnpm 11, installs backend, Admin, Portal, and E2E dependencies via pnpm, installs Chromium with Playwright, runs `pnpm test` from `e2e/`, and uploads the Playwright report artifact for seven days [@e2e-ci].

The E2E environment sets `DATABASE_URL`, `REDIS_URL`, `CANTALOUPE_URL`, `MEDIA_ROOT`, and `KATALON_SECRETS_KEY` for the Playwright command [@e2e-ci]. The workflow does not define an Elasticsearch service, so search paths that need Elasticsearch are not represented by this CI job as written [@e2e-ci].

## Current Gaps

| Area | Gap |
| --- | --- |
| E2E scheduling | Playwright runs only by manual workflow dispatch, not on every push or pull request [@e2e-ci]. |
| Browser breadth | The checked-in browser specs cover Admin login, object creation, image upload, responsive Admin layout, relation quick creation, mocked Portal search/facet behavior, and axe checks for Portal home/search pages; they do not cover IIIF viewer behavior, Portal detail-page accessibility, Admin axe checks, or Portal search against a live Elasticsearch service, which are described in [Media And IIIF](../../architecture/workflows/media-and-iiif) and [Portal Search And Facets](../../architecture/workflows/portal-search-and-facets) [@e2e-tests] [@portal-a11y-spec]. |
| Frontend breadth | Vitest and TypeScript run for both apps in CI, plus Admin ESLint. Coverage is selective, and the workflow does not build production bundles or verify visual layout [@frontend-ci] [@admin-package] [@portal-package]. |
| External services in E2E CI | The E2E workflow starts PostGIS, Redis, and Cantaloupe, but not Elasticsearch, so Elasticsearch-dependent search paths need another validation surface [@e2e-ci]. |
| Load breadth | Checked-in Locust profiles stop at 100 users and do not include heavy-load, stress, or soak runs [@performance-readme] [@performance-locust]. |
| Backup/media breadth | The automated restore drill proves PostgreSQL dump/restore mechanics for records and relations, but it does not restore real production backup archives or media files [@backup-drill-test] [@backup-drill-ci]. |
