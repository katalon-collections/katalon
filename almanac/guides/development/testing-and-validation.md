---
title: "Testing And Validation"
summary: "How to run Katalon's backend, frontend, and Playwright checks while respecting their coverage limits."
topics: [testing, development, ci]
sources:
  - id: agents
    type: file
    path: AGENTS.md
  - id: workspace-project
    type: file
    path: pyproject.toml
  - id: backend-project
    type: file
    path: backend/pyproject.toml
  - id: backend-tests
    type: file
    path: backend/tests/
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
  - id: e2e-config
    type: file
    path: e2e/playwright.config.ts
  - id: e2e-tests
    type: file
    path: e2e/tests/
  - id: backend-ci
    type: file
    path: .github/workflows/backend.yml
  - id: security-ci
    type: file
    path: .github/workflows/security.yml
  - id: e2e-ci
    type: file
    path: .github/workflows/e2e.yml
  - id: dependabot
    type: file
    path: .github/dependabot.yml
  - id: admin-audit-fix
    type: web
    url: https://github.com/karkraeg/Katalon/commit/07b33859
---

Use this guide when validating Katalon changes before handing work back or before a commit. The backend has a pytest suite with separate integration tests, the Admin and Portal apps have Vitest tests and TypeScript/Vite build checks, and the Playwright suite exercises selected Admin flows, Admin responsive behavior, relation quick-create behavior, and mocked Portal search behavior [@backend-project] [@admin-package] [@portal-package] [@e2e-tests]. Run the backend and frontend checks relevant to the changed surface, and document visual and interaction checks for UI changes. If the private maintainer supplement exists, follow its additional acceptance rules: Karl performs browser/UI and E2E checks from stated steps, and the full suite is reserved for release validation [@agents]. The successful outcome is a check set matched to the changed surface, with known gaps recorded rather than assumed away.

## Run Backend Tests

Install the backend with dev extras, then run pytest from `backend/`:

```bash
cd backend
uv pip install -e ".[dev]"
pytest tests
```

The backend package config sets `testpaths = ["tests"]` and `asyncio_mode = "auto"`, so plain `pytest` from `backend/` uses the intended backend test tree [@backend-project]. The suite includes unit-style tests for services and APIs plus `tests/integration/` tests for auth, objects, procedures, schema container fields, and vocabulary term fields [@backend-tests].

The repository root is also a uv workspace with `backend` as its only member, so root-level `uv run` can use the backend environment when a command names the backend test path explicitly [@workspace-project]. Set a test secrets key of at least 32 characters before collecting tests, as required by the project instructions and CI workflow [@agents] [@backend-ci]:

```bash
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run --no-sync pytest backend/tests -q
```

For a faster CI-shaped split, run:

```bash
cd backend
pytest tests --ignore=tests/integration
pytest tests/integration
```

The backend GitHub workflow uses that same split: unit tests run first, integration tests run after them with Redis as a service [@backend-ci]. Its third-party GitHub Actions are pinned to full commit SHAs with version comments; Dependabot is configured to open weekly `github-actions` updates so the pins do not have to be refreshed by hand [@backend-ci] [@dependabot].

## Run Frontend Unit And Component Tests

Both apps use Vitest with jsdom and React Testing Library. From either
`frontend/admin` or `frontend/portal`, run `pnpm test` once or
`pnpm test:watch` while editing. Pass a file path to limit a run, for example
`pnpm test src/lib/formVariants.test.ts` in Admin. Tests live beside the
code as `src/**/*.test.ts` or `src/**/*.test.tsx` [@admin-package]
[@portal-package] [@admin-test-config] [@portal-test-config].

Admin merges its Vite config into a separate Vitest config and cleans up
rendered components after every test [@admin-test-config] [@admin-test-setup].
Tests import Vitest helpers explicitly. Import the app's i18n module when
translations matter, and change its language explicitly in the test.
Mock browser APIs or network calls only in tests that need them; jsdom
does not verify visual layout.

The Frontend workflow runs both apps as a matrix on pushes and pull
requests. Each job installs locked dependencies, checks TypeScript, and
runs Vitest; Admin also runs ESLint [@frontend-ci]. Component tests cover
such behavior as form-variant precedence, pending confirmation actions,
and adding or removing translated values. Browser and E2E acceptance
requires separate visual and interaction checks; follow the local maintainer supplement when it assigns these checks to the maintainer [@agents].

## Check Frontend Builds

Run Admin checks from `frontend/admin`:

```bash
cd frontend/admin
pnpm install
pnpm lint
pnpm build
```

The Admin package defines `lint` as `eslint src` and `build` as `tsc && vite build` [@admin-package]. Run Portal build from `frontend/portal`:

```bash
cd frontend/portal
pnpm install
pnpm build
```

The Portal package has no lint script; its build still runs TypeScript before Vite [@portal-package]. If a frontend change affects deployment routing, pair these checks with [Admin Deploy Verification](../operations/admin-deploy-verification), because a successful Vite build does not prove nginx served the built assets from the intended base path.

Run TypeScript checks from the package directory or pass `-p` with the package
config. Calling `frontend/portal/node_modules/.bin/tsc --noEmit` from the
repository root does not pick up `frontend/portal/tsconfig.json`; it prints
compiler help instead of validating the Portal app [@portal-package].

## Check Dependency Audits

The Security workflow runs `pnpm audit --audit-level=high` separately in both
frontend package directories, so an Admin failure and a Portal failure are
diagnosed independently [@security-ci]. To reproduce that surface locally, run
the audit from each app directory:

```bash
cd frontend/admin
pnpm audit --audit-level=high

cd ../portal
pnpm audit --audit-level=high
```

The same workflow also runs `pip-audit` from `backend/`, Ruff with security
rules, and Gitleaks secret scanning; use [Test Strategy And
Gaps](../../reference/testing/test-strategy-and-gaps) for the full CI coverage
map rather than treating frontend audits as the whole security gate
[@security-ci].

If a high frontend audit is caused only by a transitive package in one app,
prefer a lockfile-only update in that app before changing direct dependencies.
The 2026-10-01 Admin incident was fixed by running `pnpm update
brace-expansion --depth 99` from `frontend/admin`; with pnpm 11,
`--depth Infinity` is invalid, and the successful fix changed only
`frontend/admin/pnpm-lock.yaml` before the local high audit and the Security CI
passed [@admin-audit-fix].

## Run Playwright E2E

Run Playwright from `e2e`:

```bash
cd e2e
pnpm install
pnpm exec playwright install chromium
pnpm test
```

The Playwright config starts the API from the repository root, the Admin dev server on `127.0.0.1:5173`, and the Portal dev server on `127.0.0.1:5174`; its default `baseURL` is `http://localhost:5173`, unless `E2E_BASE_URL` is set [@e2e-config]. Existing E2E specs cover Admin login, object creation, image upload, narrow Admin viewports, relation quick-create flows, mocked Portal search facets, metadata facet URL state, and search refinement preserving active filters [@e2e-tests].

The E2E GitHub workflow is manual dispatch, not automatic on every push or pull request. It provisions PostGIS, Redis, and Cantaloupe services, installs backend, Admin, Portal, and E2E dependencies via pnpm, installs Chromium, then runs `pnpm test` from `e2e` with database, Redis, Cantaloupe, media, and secrets environment variables [@e2e-ci] [@e2e-config].

## Match Checks To Risk

For backend-only service or API changes, run the relevant backend tests and include integration tests when database behavior, auth, media, search, or procedures are involved. For Admin changes, run Admin lint and build, then record or arrange the browser/E2E checks when the changed path is login, object creation, upload, relation creation, or responsive layout near the checked specs. For Portal search changes, run the Portal build and verify or arrange verification of the browser behavior when the change depends on real Elasticsearch data, visual layout, or route behavior outside the mocked E2E cases [@agents] [@e2e-tests].

Use [Test Strategy And Gaps](../../reference/testing/test-strategy-and-gaps) for a more compact coverage map, and use [Local Workflows](local-workflows) when a failing check is caused by the wrong stack or port rather than the code under test.
