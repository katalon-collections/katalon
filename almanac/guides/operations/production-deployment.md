---
title: "Production Deployment"
summary: "How to deploy Katalon with production compose files, run startup tasks, handle first-run credentials, and verify health."
topics: [operations, deployment, docker, security]
sources:
  - id: production-doc
    type: file
    path: docs/04_produktion.md
  - id: production-pointer
    type: file
    path: docs/production.md
  - id: prod-compose
    type: file
    path: docker-compose.prod.yml
  - id: prod-nginx
    type: file
    path: docker/nginx.prod.conf
  - id: app-main
    type: file
    path: backend/src/katalon/main.py
---

Use this guide when deploying Katalon with Docker Compose in a production-like environment. The production path is Docker-first: configure `.env`, TLS, public URLs, nginx routing, and compose overrides, then build and start `docker-compose.yml` plus `docker-compose.prod.yml`, run migrations, reindex search when needed, capture first-run credentials, and verify `/health` [@production-doc] [@prod-compose]. For background system shape, read [System Overview](../../architecture/system/system-overview); for exact compose surfaces, use [Docker Compose Surfaces](../../reference/operations/docker-compose-surfaces).

## Prepare Instance Configuration

Start from `.env.example`, then set production values before starting containers. The production checklist calls out `SECRET_KEY`, the database password, `KATALON_BASE_URL`, `CORS_ORIGINS`, TLS certificates, `docker/nginx.prod.conf`, Vite build arguments, Wikidata user-agent information, backup strategy, migrations, and first-run password rotation [@production-doc].

Keep instance-specific compose changes out of the main `docker-compose.yml`. The production guide tells operators to use `docker-compose.override.yml` for local port, mount, and environment differences so repository updates do not overwrite local deployment choices [@production-doc].

## Build And Start

Build and start the production stack from the repository root:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

The production override removes direct `api`, `admin`, and `portal` host ports and exposes only nginx on `80` and `443` [@prod-compose]. It also sets `DEBUG: "false"` on the API, passes database, Redis, Elasticsearch, Cantaloupe, public URL, first-run credential, CORS, and upload settings from the environment, and mounts TLS certs plus `docker/nginx.prod.conf` into nginx [@prod-compose].

The supplied production nginx config has one public Portal server for `example.org` and one Admin server for `admin.example.org`; both proxy `/v1/` to the API, while the Portal server also exposes `/api/` docs and `/oai` [@prod-nginx]. If the deployment uses a single-domain subpath layout instead, follow the production documentation's Vite base and nginx location changes as one consistent unit [@production-doc].

## Run Post-Start Tasks

Run migrations after the first start and after updates:

```bash
docker compose exec api alembic upgrade head
```

The production guide states that API startup does not automatically run Alembic migrations, so this step is manual [@production-doc]. After first startup or search-affecting updates, rebuild the Elasticsearch index:

```bash
curl -X POST https://deine-domain.de/v1/search/reindex
```

For object-only search field changes, the documented narrower endpoint is `POST /v1/search/reindex/object` [@production-doc].

## Handle First-Run Credentials

On startup, the API creates an admin or superuser only when no existing admin or superuser is present [@app-main]. With `KATALON_BASE_URL` set, it derives `admin@<domain>` from that URL, generates a random password, writes the credential block to `FIRST_RUN_CREDENTIALS_PATH`, logs the same block, and tells the operator to change the password immediately [@app-main]. The production guide describes the operational side: retrieve the first-run credentials, log into the Admin UI, and change the password immediately [@production-doc].

If `KATALON_BASE_URL` is empty, startup falls back to `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD` with role `admin`, which is for local-style setup rather than public production [@app-main]. The API refuses to start in non-debug mode when `SECRET_KEY` is a known default or shorter than 32 characters, or when `DEFAULT_ADMIN_PASSWORD` is a known default [@app-main].

## Verify The Deployment

Check health through nginx:

```bash
curl https://deine-domain.de/health
```

The `/health` endpoint actively checks the database and Elasticsearch, returns `{"status": "ok"}` when both are reachable, and returns HTTP `503` with `status: degraded` when a dependency fails [@app-main]. The production documentation uses that endpoint as the load-balancer-ready health check and also recommends checking API, worker, and nginx logs during startup [@production-doc].

After deployment, open the public Portal and Admin UI, then verify a write path, search, and any OAI-PMH endpoint the instance exposes. If the Admin UI is served under `/admin/` or a changed base path, run [Admin Deploy Verification](admin-deploy-verification) before treating the deployment as done. The older `docs/production.md` file is only a pointer to `docs/04_produktion.md`, so prefer the latter when deployment docs conflict [@production-pointer].
