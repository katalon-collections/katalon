---
title: "Testing And Validation"
summary: "How to run Katalon's backend, frontend, and Playwright checks while respecting their coverage limits."
topics: [testing, development, ci]
sources:
  - id: backend-project
    type: file
    path: backend/pyproject.toml
  - id: backend-tests
    type: file
    path: backend/tests/
  - id: admin-package
    type: file
    path: frontend/admin/package.json
  - id: portal-package
    type: file
    path: frontend/portal/package.json
  - id: e2e-config
    type: file
    path: e2e/playwright.config.ts
  - id: e2e-tests
    type: file
    path: e2e/tests/
  - id: backend-ci
    type: file
    path: .github/workflows/backend.yml
  - id: e2e-ci
    type: file
    path: .github/workflows/e2e.yml
  - id: dependabot
    type: file
    path: .github/dependabot.yml
---

Use this guide when validating Katalon changes before handing work back or before a commit. The backend has a pytest suite with separate integration tests, the Admin and Portal apps have TypeScript/Vite build checks, and the Playwright suite exercises a small set of Admin browser flows [@backend-project] [@admin-package] [@portal-package] [@e2e-tests]. The successful outcome is a check set matched to the changed surface, with known gaps recorded rather than assumed away.

## Run Backend Tests From `backend/`

Install the backend with dev extras, then run pytest from `backend/`:

```bash
cd backend
uv pip install -e ".[dev]"
pytest tests
```

The backend package config sets `testpaths = ["tests"]` and `asyncio_mode = "auto"`, so plain `pytest` from `backend/` uses the intended backend test tree [@backend-project]. The suite includes unit-style tests for services and APIs plus `tests/integration/` tests for auth, objects, procedures, schema container fields, and vocabulary term fields [@backend-tests].

For a faster CI-shaped split, run:

```bash
cd backend
pytest tests --ignore=tests/integration
pytest tests/integration
```

The backend GitHub workflow uses that same split: unit tests run first, integration tests run after them with Redis as a service [@backend-ci]. Its third-party GitHub Actions are pinned to full commit SHAs with version comments; Dependabot is configured to open weekly `github-actions` updates so the pins do not have to be refreshed by hand [@backend-ci] [@dependabot].

## Check Frontend Builds

Run Admin checks from `frontend/admin`:

```bash
cd frontend/admin
npm install
npm run lint
npm run build
```

The Admin package defines `lint` as `eslint src --ext .ts,.tsx` and `build` as `tsc && vite build` [@admin-package]. Run Portal build from `frontend/portal`:

```bash
cd frontend/portal
npm install
npm run build
```

The Portal package has no lint script; its build still runs TypeScript before Vite [@portal-package]. If a frontend change affects deployment routing, pair these checks with [Admin Deploy Verification](../operations/admin-deploy-verification), because a successful Vite build does not prove nginx served the built assets from the intended base path.

## Run Playwright E2E

Run Playwright from `e2e`:

```bash
cd e2e
npm install
npx playwright install chromium
npm run test
```

The Playwright config starts `docker compose up -d api` from the repository root and starts the Admin dev server on `127.0.0.1:5173`; its default `baseURL` is `http://localhost:5173`, unless `E2E_BASE_URL` is set [@e2e-config]. Existing E2E specs cover Admin login, object creation, image upload, and shared helpers [@e2e-tests].

The E2E GitHub workflow is manual dispatch, not automatic on every push or pull request. It provisions PostGIS, Redis, and Cantaloupe services, installs backend, Admin, and E2E dependencies, installs Chromium, then runs `npm run test` from `e2e` with database, Redis, Cantaloupe, media, and secrets environment variables [@e2e-ci].

## Match Checks To Risk

For backend-only service or API changes, run backend tests and include integration tests when database behavior, auth, media, search, or procedures are involved. For Admin changes, run Admin lint and build, then Playwright when the changed path is login, object creation, upload, or another browser flow close to those specs. For Portal changes, run the Portal build and add manual browser verification if the change is visual or route-driven because the current Playwright suite is Admin-focused [@e2e-tests].

Use [Test Strategy And Gaps](../../reference/testing/test-strategy-and-gaps) for a more compact coverage map, and use [Local Workflows](local-workflows) when a failing check is caused by the wrong stack or port rather than the code under test.
