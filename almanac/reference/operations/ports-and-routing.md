---
title: "Ports And Routing"
summary: "Reference for Katalon local ports, Docker routing, and the Admin base-path deployment rule."
topics: [reference, operations, routing, docker]
sources:
  - id: agents
    type: file
    path: AGENTS.md
  - id: dev-doc
    type: file
    path: .agents/DEV.md
  - id: compose
    type: file
    path: docker-compose.yml
  - id: dev-compose
    type: file
    path: docker-compose.dev.yml
  - id: nginx
    type: file
    path: docker/nginx.conf
  - id: portal-nginx
    type: file
    path: docker/nginx.portal.conf
  - id: admin-dockerfile
    type: file
    path: docker/Dockerfile.admin
  - id: admin-nginx
    type: file
    path: docker/nginx.admin.conf
  - id: admin-vite
    type: file
    path: frontend/admin/vite.config.ts
  - id: portal-vite
    type: file
    path: frontend/portal/vite.config.ts
  - id: app
    type: file
    path: backend/src/katalon/main.py
  - id: portal-client
    type: file
    path: frontend/portal/src/api/client.ts
---

Katalon has three relevant routing surfaces: the production-like Compose stack on nginx port 80, direct container ports for built frontend images, and the dev-compose Vite ports. The production-like stack routes `/admin/` to the Admin container, `/` to the Portal container, `/v1/`, `/portal/v1/`, and `/api/` to the API without stripping their path prefixes, and `/iiif/` to Cantaloupe [@nginx]. The main deployment gotcha is the Admin build base path: `docker/Dockerfile.admin` builds Vite with `VITE_BASE_PATH=/admin/`, and AGENTS marks that value as deployment-critical because wrong asset paths can make the Admin UI load a blank shell through nginx [@admin-dockerfile] [@agents].

## Production-Like Compose

| Surface | URL or port | Route owner |
|---|---|---|
| Portal | `http://localhost/` | outer nginx `location /` to `portal` |
| Admin | `http://localhost/admin/` | outer nginx `location /admin/` to `admin` after path rewrite |
| API routes | `http://localhost/v1/...` | outer nginx `location /v1/` to `api:8000` |
| Portal public API | `http://localhost/portal/v1/...` | outer nginx `location /portal/v1/` to `api:8000` |
| API docs | `http://localhost/api/docs` | outer nginx `location /api/` to `api:8000`, preserving `/api/...` |
| IIIF | `http://localhost/iiif/...` | outer nginx `location /iiif/` to `cantaloupe:8182` |
| HTTPS | `https://localhost/...` | outer nginx also listens on 443 with a self-signed dev cert from `docker/certs/` (`make certs`) |
| Admin direct port | `http://localhost:3000` | Compose `admin` port mapping to container port 80 |
| Portal direct port | `http://localhost:3001` | Compose `portal` port mapping to container port 80 |

The base Compose file publishes `admin` on `3000:80`, `portal` on `3001:80`, and outer `nginx` on `80:80` and `443:443` [@compose]. `api` no longer publishes a host port in the base stack; it is reachable only through nginx or from other containers on the Compose network at `api:8000` [@compose]. For normal browser checks without an explicit dev-stack target, AGENTS says to use `http://localhost/admin/` and `http://localhost/` instead of direct frontend container ports [@agents].

FastAPI mounts the anonymous Portal read model at `/portal/v1`, and the Portal client uses `/portal/v1` as its API prefix [@app] [@portal-client]. Both outer nginx and the Portal container nginx define slash-terminated `location /portal/v1/` proxies [@nginx] [@portal-nginx]. Operational checks should therefore hit a real child endpoint such as `http://localhost/portal/v1/objects`; `http://localhost/portal/v1` without the trailing slash is not the API index and can fall through to the Portal SPA route.

FastAPI configures Swagger UI, ReDoc, and the OpenAPI schema at `/api/docs`, `/api/redoc`, and `/api/openapi.json` [@app]. The outer nginx `/api/` location must preserve that prefix when proxying to the API; stripping it makes those FastAPI application-level paths miss and return 404 even when the API container itself is healthy [@nginx] [@app].

## Dev Compose

| Surface | URL or port | Route owner |
|---|---|---|
| Admin Vite | `http://localhost:4000` | dev override maps host 4000 to Vite 5173 |
| Portal Vite | `http://localhost:4001` | dev override maps host 4001 to Vite 5174 |
| API | `http://localhost:8000` | dev override keeps API on 8000 |
| PostgreSQL | `localhost:5432` | dev override publishes db |
| Redis | `localhost:6379` | dev override publishes redis |
| Elasticsearch | `http://localhost:9200` | dev override publishes Elasticsearch |
| Cantaloupe | `http://localhost:8182` | dev override publishes Cantaloupe |

`docker-compose.dev.yml` swaps the frontend services to Vite dev containers and maps Admin `4000:5173` and Portal `4001:5174` [@dev-compose]. The Vite configs keep their internal dev server ports at 5173 for Admin and 5174 for Portal [@admin-vite] [@portal-vite]. The development guide documents the Docker dev stack as the recommended live-reload workflow and the local workflow as separate terminals for API, worker, Admin Vite, and Portal Vite [@dev-doc]. See [Local Workflows](../../guides/development/local-workflows) for the operational procedure.

## Standalone Local Development

| Process | Default local address |
|---|---|
| API with `uvicorn katalon.main:app --reload --port 8000` | `http://localhost:8000` |
| Admin Vite with `npm run dev` | `http://localhost:5173` |
| Portal Vite with `npm run dev` | `http://localhost:5174` |

The local workflow starts backing services through Compose, then runs the API, worker, and both frontend dev servers directly on the host [@dev-doc]. Admin and Portal Vite proxy `/v1` to `API_PROXY_TARGET`, `VITE_API_URL`, or `http://localhost:8000` in that order [@admin-vite] [@portal-vite].

## Admin Base-Path Rule

The production Admin image runs `VITE_BASE_PATH=/admin/ npm run build`; Vite reads `VITE_BASE_PATH` into its `base` setting [@admin-dockerfile] [@admin-vite]. Outer nginx strips the `/admin/` prefix before proxying to the Admin container, and the Admin container's nginx serves built assets from `/assets/` inside that container [@nginx] [@admin-nginx].

Do not treat `docker/Dockerfile.admin`, `docker/nginx.admin.conf`, and `frontend/admin/vite.config.ts` as independent files. AGENTS requires checking that `VITE_BASE_PATH` and nginx locations remain consistent before changing them, then verifying the deployed Admin page and its JS/CSS requests [@agents]. The verification procedure is in [Admin Deploy Verification](../../guides/operations/admin-deploy-verification).
