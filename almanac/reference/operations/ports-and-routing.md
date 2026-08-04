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
---

Katalon has three relevant routing surfaces: the production-like Compose stack on nginx port 80, direct container ports for built frontend images, and the dev-compose Vite ports. The production-like stack routes `/admin/` to the Admin container, `/` to the Portal container, `/v1/` to the API, `/api/` to the API after stripping `/api`, and `/iiif/` to Cantaloupe [@nginx]. The main deployment gotcha is the Admin build base path: `docker/Dockerfile.admin` builds Vite with `VITE_BASE_PATH=/admin/`, and AGENTS marks that value as deployment-critical because wrong asset paths can make the Admin UI load a blank shell through nginx [@admin-dockerfile] [@agents].

## Production-Like Compose

| Surface | URL or port | Route owner |
|---|---|---|
| Portal | `http://localhost/` | outer nginx `location /` to `portal` |
| Admin | `http://localhost/admin/` | outer nginx `location /admin/` to `admin` after path rewrite |
| API routes | `http://localhost/v1/...` | outer nginx `location /v1/` to `api:8000` |
| API docs | `http://localhost/api/docs` | outer nginx strips `/api/` before proxying |
| IIIF | `http://localhost/iiif/...` | outer nginx `location /iiif/` to `cantaloupe:8182` |
| API direct port | `http://localhost:8000` | Compose `api` port mapping |
| Admin direct port | `http://localhost:3000` | Compose `admin` port mapping to container port 80 |
| Portal direct port | `http://localhost:3001` | Compose `portal` port mapping to container port 80 |

The base Compose file publishes `api` on `8000:8000`, `admin` on `3000:80`, `portal` on `3001:80`, and outer `nginx` on `80:80` [@compose]. For normal browser checks without an explicit dev-stack target, AGENTS says to use `http://localhost/admin/` and `http://localhost/` instead of direct frontend container ports [@agents].

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
