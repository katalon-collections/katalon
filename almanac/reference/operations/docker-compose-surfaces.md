---
title: "Docker Compose Surfaces"
summary: "Lookup reference for Katalon's Compose stacks, service ports, mounts, health checks, and production overrides."
topics: [reference, operations, docker, deployment]
sources:
  - id: compose-base
    type: file
    path: docker-compose.yml
  - id: compose-dev
    type: file
    path: docker-compose.dev.yml
  - id: compose-prod
    type: file
    path: docker-compose.prod.yml
  - id: compose-cantaloupe
    type: file
    path: docker-compose.cantaloupe.yml
  - id: compose-override-example
    type: file
    path: docker-compose.override.yml.example
---

Katalon's Compose surface is split into a base stack, a development override, a production override, a Cantaloupe override, and a local customization example. The base stack defines the service graph for PostgreSQL/PostGIS, Redis, Elasticsearch, Cantaloupe, FastAPI, Celery workers, two Vite-built frontends, nginx, and backups; the overrides change exposure, rebuild behavior, TLS/routing, and instance-specific settings without replacing the base service model [@compose-base] [@compose-dev] [@compose-prod].

## Base Stack

`docker-compose.yml` is the normal stack described by the [System Overview](../../architecture/system/system-overview). It defines:

| Service | Image or build | Main role | External port in base stack | Health check |
| --- | --- | --- | --- | --- |
| `db` | `postgis/postgis:16-3.4` | PostgreSQL 16 with PostGIS, backed by `db_data` | none | `pg_isready` |
| `redis` | `redis:7-alpine` | broker/cache dependency for async work | none | `redis-cli ping` |
| `elasticsearch` | Elasticsearch 8.13.4 | single-node search index | none | cluster health over `localhost:9200` |
| `cantaloupe` | `islandora/cantaloupe:main` | IIIF Image API service over mounted media | none | `curl` against `/iiif/3` |
| `api` | `docker/Dockerfile.backend` | FastAPI application | `8000:8000` | `curl` against `/health` |
| `worker` | `docker/Dockerfile.worker` | Celery worker process | none | none |
| `beat` | `docker/Dockerfile.worker` | Celery beat scheduler | none | none |
| `admin` | `docker/Dockerfile.admin` | built Admin frontend served by nginx-in-container | `3000:80` | `wget` against `/index.html` |
| `portal` | `docker/Dockerfile.portal` | built Portal frontend served by nginx-in-container | `3001:80` | `wget` against `/index.html` |
| `nginx` | `nginx:alpine` | outer nginx container using `docker/nginx.conf` | `80:80` | none |
| `backup` | `postgis/postgis:16-3.4` | scheduled database/media backup runner | none | none |

The base stack keeps database and Elasticsearch state in named volumes `db_data` and `es_data`; media is bind-mounted from `${MEDIA_ROOT:-/srv/katalon/media}` into the API, worker, Cantaloupe, and backup services [@compose-base]. The backup service also mounts `docker/backup.sh` read-only and writes to `${BACKUP_ROOT:-/srv/katalon/backups}` [@compose-base].

## Dependency Edges

The API waits for healthy `db`, `redis`, and `cantaloupe`; the worker and beat wait for the same services; Admin and Portal wait for healthy API; outer nginx waits for healthy API, Admin, and Portal [@compose-base]. In the development override, API and worker also wait for healthy Elasticsearch, and Cantaloupe is allowed with `service_started` rather than its base health condition [@compose-dev].

## Development Override

`docker-compose.dev.yml` exposes infrastructure and switches API and frontend services to development images and bind mounts. It publishes PostgreSQL on `5432`, Redis on `6379`, Elasticsearch on `9200`, Cantaloupe on `8182`, API on `8000`, Admin on `4000`, and Portal on `4001` [@compose-dev].

The development API uses `docker/Dockerfile.backend.dev`, bind-mounts `backend/src` and `backend/migrations`, and runs `uvicorn katalon.main:app --reload` [@compose-dev]. The development Admin and Portal use their separate frontend directories as build contexts, mount source directories plus anonymous `node_modules` volumes, and proxy API requests through `API_PROXY_TARGET=http://api:8000` [@compose-dev].

## Production Override

`docker-compose.prod.yml` is the production override used by the [Production Deployment](../../guides/operations/production-deployment) guide. It sets restart policies, memory limits, explicit environment variables, TLS nginx config, and `80`/`443` publication on nginx [@compose-prod]. It removes direct published ports from `api`, `admin`, and `portal` with `ports: !reset []`, so production access goes through nginx [@compose-prod].

Production Elasticsearch uses a fixed `ES_JAVA_OPTS=-Xms1g -Xmx1g` and a `2g` memory limit; the API, worker, Cantaloupe, database, Redis, and nginx each get smaller service-specific limits [@compose-prod]. The production nginx mounts `docker/nginx.prod.conf` and `docker/certs/` read-only [@compose-prod].

## IIIF Override

`docker-compose.cantaloupe.yml` is a narrow IIIF override. It forces filesystem lookup settings, sets Cantaloupe's public base URI to `http://localhost`, and points API and worker at Cantaloupe internally on `http://cantaloupe:8182`; public manifests use nginx's `http://localhost/iiif/...` route [@compose-cantaloupe].

## Instance Override

`docker-compose.override.yml.example` documents local instance customization through Docker Compose's automatic override merge. Its examples change nginx's HTTPS port, add an API environment variable, and replace the database storage path with a host mount [@compose-override-example].
