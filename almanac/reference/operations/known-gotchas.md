---
title: "Known Gotchas"
summary: "Operational traps that should be checked before testing, deploying, or repairing the Katalon stack."
topics: [reference, operations, testing, deployment]
sources:
  - id: cli
    type: file
    path: backend/src/katalon/management/cli.py
  - id: file-field-attachments-concept
    type: file
    path: almanac/concepts/metadata/file-field-attachments.md
  - id: agents
    type: file
    path: AGENTS.md
  - id: backend-pyproject
    type: file
    path: backend/pyproject.toml
  - id: compose
    type: file
    path: docker-compose.yml
  - id: backend-dockerfile
    type: file
    path: docker/Dockerfile.backend
  - id: worker-dockerfile
    type: file
    path: docker/Dockerfile.worker
  - id: admin-dockerfile
    type: file
    path: docker/Dockerfile.admin
  - id: portal-dockerfile
    type: file
    path: docker/Dockerfile.portal
  - id: public-image-workflow
    type: file
    path: .github/workflows/public-container-images.yml
  - id: migration-0051
    type: file
    path: backend/migrations/versions/0051_field_show_in_list_default_false.py
  - id: dev-compose
    type: file
    path: docker-compose.dev.yml
  - id: nginx-dev
    type: file
    path: docker/nginx.dev.conf
  - id: caddyfile-example
    type: file
    path: Caddyfile.example
  - id: prod-compose
    type: file
    path: docker-compose.prod.yml
  - id: nginx
    type: file
    path: docker/nginx.conf
  - id: admin-nginx
    type: file
    path: docker/nginx.admin.conf
  - id: media-api
    type: file
    path: backend/src/katalon/api/v1/media.py
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
  - id: pg-restore-doc
    type: web
    url: https://www.postgresql.org/docs/16/app-pgrestore.html
---

Katalon's durable operational gotchas are mostly about choosing the right runtime surface before checking behavior: use the correct Compose port, preserve Admin's `/admin/` asset base path, check application upload limits before nginx, rebuild backend images when migrations change, confirm public release images passed their security gate, reload nginx and frontend containers after route-prefix changes, run backend commands from `backend/`, run `katalon-manage` against a database host that is reachable from the current process, keep the known `click-didyoumean` pin, provide `KATALON_SECRETS_KEY` for pytest, read `pg_restore` errors before trusting a restored database, treat code-level rebranding as an operational migration, and never delete database volumes without explicit approval [@agents] [@gotcha-click] [@gotcha-secrets] [@backend-pyproject] [@compose] [@dev-compose] [@backend-dockerfile] [@public-image-workflow] [@media-api] [@pg-restore-doc]. Use this page before following deployment, testing, or [database escalation](../../guides/operations/db-problem-escalation) work.

Background-configuration details move with `.env` resolution: `Settings` now reads `backend/.env` and the repository root `.env` from absolute source-relative paths, so backend commands are no longer coupled to a particular working directory for config [@config]. `katalon-manage` runs from the repo root with `uv run katalon-manage` or `backend/.venv/bin/katalon-manage`, but only if the `DATABASE_URL` it reads points to a host reachable from that process [@agents] [@backend-pyproject] [@config]. A checkout `.env` that uses Compose's `db` hostname works inside containers and fails from the macOS host because `db` exists only on the Compose network; use `docker compose exec api katalon-manage ...` for the normal Compose surface, or override `DATABASE_URL` to the dev stack's exposed `localhost:5432` when deliberately running from the host [@agents] [@compose] [@dev-compose]. The launcher reports a missing or too-short `KATALON_SECRETS_KEY` as one readable line instead of a Pydantic stack trace [@management-runner] [@errors].

## Ports And Stack Choice

Root project instructions define the current port rule: `http://localhost/admin/` and `http://localhost/` are the normal production-like browser targets through the outer nginx on port `80`; direct `http://localhost:3000` and `http://localhost:3001` hit the Admin and Portal containers and are for container debugging only; `http://localhost:4000` and `http://localhost:4001` belong to the development Compose stack [@agents].

The Portal public API prefix is `/portal/v1` in the frontend client, and outer nginx only proxies that surface through the slash-terminated `location /portal/v1/` block [@portal-client] [@nginx]. FastAPI's documentation routes are configured with the `/api` prefix, so outer nginx must not strip `/api/` before proxying; otherwise `/api/docs`, `/api/redoc`, and `/api/openapi.json` return 404 through nginx even though the FastAPI app has those paths registered [@app] [@nginx]. After changing these routes, recreate or reload the affected nginx/Portal containers before testing through `http://localhost/`; otherwise the browser can still see the old route table or old frontend bundle. Test concrete endpoints such as `http://localhost/portal/v1/objects` and `http://localhost/api/docs`, not bare `/portal/v1`.

For the `katalon.local` dev hostname, `docker/nginx.dev.conf` handles bare `/admin` by redirecting it to `/admin/`; the optional host-level `Caddyfile.example` carries the same redirect before its `/admin/*` proxy [@nginx-dev] [@caddyfile-example]. Without this trailing-slash redirect, `/admin` falls through to the Portal catch-all while the URL still looks like Admin.

## Cantaloupe Derivative Cache

The base Compose stack sets `CANTALOUPE_FILESYSTEMCACHE_PATHNAME=/data/cache` and mounts `/data` from the named volume `cantaloupe_cache` (or `CANTALOUPE_CACHE_DIR`), so derivatives survive restarts; a one-shot `cantaloupe-cache-init` service in the same image creates `/data/cache` and hands entries with a wrong owner to the image's `cantaloupe` user before Cantaloupe starts. Setting `CANTALOUPE_FILESYSTEMCACHE_PATHNAME=/tmpfs/cache` switches to the always-mounted tmpfs instead (mode `1023` in Compose = octal `1777`; Compose reads `mode` as a decimal integer, so the earlier `1777` produced unusable permissions). Production reuses that service definition [@compose] [@prod-compose]. The Cantaloupe health check creates and removes a file below `/data/cache`, so cache writability is part of service readiness [@compose]. Older deployments may still have a root-owned filesystem cache while the Cantaloupe JVM runs as the `cantaloupe` user. In that state `info.json` and thumbnails may work, but full-size IIIF requests can return HTTP 200 with zero bytes; `cantaloupe` logs `AccessDeniedException` from `FilesystemCache`.

For current deployments, recreate Cantaloupe so the init step repairs ownership of the cache volume:

```bash
docker compose up -d --force-recreate cantaloupe-cache-init cantaloupe
```

For older deployments, check and repair the cache without touching the media volume:

```bash
docker compose logs cantaloupe --tail=100 | grep -E "AccessDeniedException|FilesystemCache"
docker compose exec cantaloupe sh -c 'p="${CANTALOUPE_FILESYSTEMCACHE_PATHNAME:-/data/cache}"; ls -ld "$p"'
docker compose exec cantaloupe sh -c 'p="${CANTALOUPE_FILESYSTEMCACHE_PATHNAME:-/data/cache}"; chown -R cantaloupe:cantaloupe "$p" && chmod -R u+rwX "$p"'
```

Verify a real IIIF derivative returns a positive byte count, not only `info.json`.

## Stale Backend Images And Alembic Revisions

The API image copies `backend/migrations/` at build time, so a running or locally tagged `katalon-api` image can lack a migration file that exists in the checkout [@backend-dockerfile]. If the database already records that revision, startup migrations fail before the API becomes healthy; revision `0051` is one concrete migration in the current tree and depends on `0050` [@migration-0051].

When logs show an Alembic message like `Can't locate revision identified by '0051'`, compare the image build time with the checkout and rebuild the backend service images instead of changing database state:

```bash
docker compose build api worker beat
docker compose up -d
```

This is an image/source mismatch check, not a reason to delete volumes. The database-volume rule still applies [@agents].

## Public Release Image Gates

A pushed public tag is not enough to make a release installable. The public repository's container workflow runs only on `katalon-collections/katalon`, validates that the tag matches backend and frontend package versions, builds `api`, `worker`, `admin`, and `portal` images locally, scans each image with Trivy for `CRITICAL,HIGH` vulnerabilities using `ignore-unfixed: true`, and pushes the GHCR image only after that scan passes [@public-image-workflow]. After the image matrix succeeds, the same workflow pulls the just-pushed Admin and Portal images, runs `scripts/smoke-test-admin-routing.sh`, generates `katalon-release.json`, and creates the GitHub Release asset [@public-image-workflow].

When a public release tag exists but `katalon-cli` cannot pull the corresponding images or release metadata, check the public container workflow before retagging or changing installer metadata. Base-image CVEs can block the push stage even when the source export and tag were published correctly, and an Admin base-path regression can fail the routing smoke test after images were built [@public-image-workflow]. The current production Dockerfiles upgrade Debian or Alpine packages in the runtime image layers before Trivy scans run [@backend-dockerfile] [@worker-dockerfile] [@admin-dockerfile] [@portal-dockerfile] [@public-image-workflow].

## Object Media Upload Size

Object media uploads hit the backend's `settings.max_upload_size_mb` check while the file is streamed, before Katalon creates the `MediaFile` row or queues IIIF work [@media-api]. The source setting defaults to 100 MB, the main Compose stack sets `MAX_UPLOAD_SIZE_MB` to 200 MB when the operator does not override it, and the outer nginx allows 500 MB request bodies; the direct Admin nginx config has its own 200 MB body limit and is a debugging surface, not the normal production-like browser path [@config] [@compose] [@nginx] [@admin-nginx] [@agents].

For large TIFF failures, check the effective `MAX_UPLOAD_SIZE_MB` in the API container and the path used to reach the upload endpoint before raising proxy limits. The importer has a separate `IMPORTER_MAX_UPLOAD_SIZE_MB` setting and should not be used as evidence for object media upload limits [@config] [@media-api].

`file`-field attachments have their own limit, `ATTACHMENT_MAX_UPLOAD_MB` (default 200). A 413 on a file field is not a media limit and is not fixed by `MAX_UPLOAD_SIZE_MB`. Attachments are not removed when a file is taken out of its field; that happens only when `katalon-manage attachments-gc` runs, and the command must be scheduled by the operator [@config] [@cli] [@file-field-attachments-concept].

## Admin Asset Base Path

Admin's production image needs `VITE_BASE_PATH=/admin/` because the outer nginx routes Admin under `/admin/` [@agents]. If that build argument or adjacent nginx/Vite routing changes, Admin can build successfully while runtime JS and CSS paths point at `/assets/` and miss the Admin container [@agents] [@gotcha-vite].

Before changing `docker/Dockerfile.admin`, `docker/nginx.admin.conf`, or `frontend/admin/vite.config.ts`, check that `VITE_BASE_PATH` and nginx `location` blocks still match, then verify the deployed `/admin/` URL and its JS/CSS requests [@agents]. The operational verification lives in the Admin deploy guide.

## Backend Command Location

Backend Python commands should run from `backend/`, not the repository root, to keep a single, predictable interpreter [@agents]. This applies to pytest, migrations, dependency syncs, and ad hoc backend commands.

Since the repository root is a uv workspace (`pyproject.toml` with `members = ["backend"]`), `uv run` from the root resolves the backend package and command environment correctly; the explicit `backend/.venv/bin/katalon-manage` interpreter also works and reads `.env` from absolute source paths [@backend-pyproject] [@config] [@management-runner]. That does not make Compose service names reachable from the host. If `.env` contains `DATABASE_URL=...@db:5432/...`, host-side `uv run katalon-manage ...` fails at DNS lookup; run the command in the API container with `docker compose exec api katalon-manage ...` or override `DATABASE_URL` to `...@localhost:5432/...` in the dev stack where `docker-compose.dev.yml` exposes PostgreSQL on host port `5432` [@agents] [@compose] [@dev-compose].

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

## Restore Error Interpretation

`pg_restore` can continue after an error and report the total error count at the end unless `--exit-on-error` is used, so a noisy custom-format restore is not automatically a total failure or a verified success [@pg-restore-doc]. When `--clean` is involved, object-drop errors can appear before later restore work continues [@pg-restore-doc]. Treat that state as inconclusive: follow [Backup And Restore](../../guides/operations/backup-and-restore), compare restored data with the source instance, rebuild search only after the database is trusted, and do not use destructive database drops as a shortcut around cleanup messages [@agents].

## Code-Level Rebranding

A code-level rename from `katalon` is not a text-only documentation pass. The name is embedded in the Python package and CLI entry point, Compose commands and defaults, container media paths, database defaults, environment variable names, and frontend package names [@backend-pyproject] [@compose] [@dev-compose] [@prod-compose] [@admin-package] [@portal-package].

Before such a rename, separate source-code/package changes from deployed-state migration. Existing database names, Compose volumes, host media paths, `.env` values, and any production backup paths may be live state; do not fold them into a blind search-and-replace or volume reset [@compose] [@agents].
