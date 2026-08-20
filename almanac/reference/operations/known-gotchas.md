---
title: "Known Gotchas"
summary: "Operational traps that should be checked before testing, deploying, or repairing the Katalon stack."
topics: [reference, operations, testing, deployment]
sources:
  - id: agents
    type: file
    path: AGENTS.md
  - id: backend-pyproject
    type: file
    path: backend/pyproject.toml
  - id: compose
    type: file
    path: docker-compose.yml
  - id: dev-compose
    type: file
    path: docker-compose.dev.yml
  - id: prod-compose
    type: file
    path: docker-compose.prod.yml
  - id: nginx
    type: file
    path: docker/nginx.conf
  - id: app
    type: file
    path: backend/src/katalon/main.py
  - id: portal-client
    type: file
    path: frontend/portal/src/api/client.ts
  - id: admin-package
    type: file
    path: frontend/admin/package.json
  - id: portal-package
    type: file
    path: frontend/portal/package.json
  - id: gotcha-vite
    type: file
    path: .agents/knowledge/gotchas/vite-base-path.md
  - id: gotcha-click
    type: file
    path: .agents/knowledge/gotchas/click-didyoumean-lock.md
  - id: gotcha-secrets
    type: file
    path: .agents/knowledge/gotchas/pytest-secrets-key.md
  - id: config
    type: file
    path: backend/src/katalon/config.py
  - id: management-runner
    type: file
    path: backend/src/katalon/management/runner.py
  - id: errors
    type: file
    path: backend/src/katalon/errors.py
---

Katalon's durable operational gotchas are mostly about choosing the right runtime surface before checking behavior: use the correct Compose port, preserve Admin's `/admin/` asset base path, reload nginx and frontend containers after route-prefix changes, run backend commands from `backend/`, keep the known `click-didyoumean` pin, provide `KATALON_SECRETS_KEY` for pytest, treat code-level rebranding as an operational migration, and never delete database volumes without explicit approval [@agents] [@gotcha-click] [@gotcha-secrets] [@backend-pyproject] [@compose]. Use this page before following deployment, testing, or [database escalation](../../guides/operations/db-problem-escalation) work.

Background-configuration details move with `.env` resolution: `Settings` now reads `backend/.env` and the repository root `.env` from absolute source-relative paths, so backend commands are no longer coupled to a particular working directory for config [@config]. `katalon-manage` runs from the repo root with `backend/.venv/bin/katalon-manage` and reports a missing or short `KATALON_SECRETS_KEY` as one readable line via `backend/src/katalon/management/runner.py` [@management-runner] [@errors].

## Ports And Stack Choice

Root project instructions define the current port rule: `http://localhost/admin/` and `http://localhost/` are the normal production-like browser targets through the outer nginx on port `80`; direct `http://localhost:3000` and `http://localhost:3001` hit the Admin and Portal containers and are for container debugging only; `http://localhost:4000` and `http://localhost:4001` belong to the development Compose stack [@agents].

The Portal public API prefix is `/portal/v1` in the frontend client, and outer nginx only proxies that surface through the slash-terminated `location /portal/v1/` block [@portal-client] [@nginx]. FastAPI's documentation routes are configured with the `/api` prefix, so outer nginx must not strip `/api/` before proxying; otherwise `/api/docs`, `/api/redoc`, and `/api/openapi.json` return 404 through nginx even though the FastAPI app has those paths registered [@app] [@nginx]. After changing these routes, recreate or reload the affected nginx/Portal containers before testing through `http://localhost/`; otherwise the browser can still see the old route table or old frontend bundle. Test concrete endpoints such as `http://localhost/portal/v1/objects` and `http://localhost/api/docs`, not bare `/portal/v1`.

## Cantaloupe Derivative Cache

The base Compose stack mounts the Cantaloupe derivative cache at `/var/lib/cantaloupe/cache`, and production reuses that service definition [@compose] [@prod-compose]. The current stack uses a disposable `tmpfs`, avoiding ownership problems on newly created volumes. Older deployments may still have a root-owned named volume while the Cantaloupe JVM runs as the `cantaloupe` user. In that state `info.json` and thumbnails may work, but full-size IIIF requests can return HTTP 200 with zero bytes; `cantaloupe` logs `AccessDeniedException` from `FilesystemCache`.

For current deployments, recreate only Cantaloupe so the tmpfs mount takes effect:

```bash
docker compose up -d --force-recreate cantaloupe
```

For older deployments, check and repair the cache without touching the media volume:

```bash
docker compose logs cantaloupe --tail=100 | grep -E "AccessDeniedException|FilesystemCache"
docker compose exec cantaloupe ls -ld /var/lib/cantaloupe/cache
docker compose exec cantaloupe sh -c 'chown -R cantaloupe:cantaloupe /var/lib/cantaloupe/cache && chmod -R u+rwX /var/lib/cantaloupe/cache'
```

Verify a real IIIF derivative returns a positive byte count, not only `info.json`.

## Admin Asset Base Path

Admin's production image needs `VITE_BASE_PATH=/admin/` because the outer nginx routes Admin under `/admin/` [@agents]. If that build argument or adjacent nginx/Vite routing changes, Admin can build successfully while runtime JS and CSS paths point at `/assets/` and miss the Admin container [@agents] [@gotcha-vite].

Before changing `docker/Dockerfile.admin`, `docker/nginx.admin.conf`, or `frontend/admin/vite.config.ts`, check that `VITE_BASE_PATH` and nginx `location` blocks still match, then verify the deployed `/admin/` URL and its JS/CSS requests [@agents]. The operational verification lives in the Admin deploy guide.

## Backend Command Location

Backend Python commands should run from `backend/`, not the repository root, to keep a single, predictable interpreter [@agents]. This applies to pytest, migrations, dependency syncs, and ad hoc backend commands.

Since the repository root is a uv workspace (`pyproject.toml` with `members = ["backend"]`), `uv run` from the root resolves the backend environment correctly and `katalon-manage` is directly usable there (`uv run katalon-manage ...`); the explicit `backend/.venv/bin/katalon-manage` interpreter also works and reads `.env` from absolute source paths [@backend-pyproject] [@config] [@management-runner].

## uv Lock Pin

The known `uv` dependency trap is `click-didyoumean`: the repository note records an inconsistent lock state where the entry version `0.3.2` points at `click_didyoumean-0.3.1` files [@gotcha-click]. Since the repository root is a uv workspace (`pyproject.toml` with `members = ["backend"]`), the effective lock is the root `uv.lock`; `backend/uv.lock` is superseded [@config]. Keep `click-didyoumean==0.3.1` pinned in `backend/pyproject.toml` until the lock condition is deliberately checked and fixed [@agents] [@gotcha-click].

## pytest Secrets Key

Backend pytest collection needs `KATALON_SECRETS_KEY`; without it, imports that instantiate settings can fail before any tests run [@gotcha-secrets]. The documented local command shape is:

```bash
cd backend
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run pytest -q
```

The CI backend workflow sets the same environment variable globally, but local shells do not inherit that automatically [@gotcha-secrets]. Because `Settings` now reads the repository root `.env` from an absolute path, running from the repo root (where `.env` lives) can satisfy the requirement without exporting it by hand [@config].

## Database Volumes

Do not run `docker compose down -v`, delete database volumes, or recreate database storage as a repair shortcut without explicit approval [@agents]. The required sequence for database problems is to read container logs, identify the root cause, present options, and act only after approval [@agents].

## Code-Level Rebranding

A code-level rename from `katalon` is not a text-only documentation pass. The name is embedded in the Python package and CLI entry point, Compose commands and defaults, container media paths, database defaults, environment variable names, and frontend package names [@backend-pyproject] [@compose] [@dev-compose] [@prod-compose] [@admin-package] [@portal-package].

Before such a rename, separate source-code/package changes from deployed-state migration. Existing database names, Compose volumes, host media paths, `.env` values, and any production backup paths may be live state; do not fold them into a blind search-and-replace or volume reset [@compose] [@agents].
