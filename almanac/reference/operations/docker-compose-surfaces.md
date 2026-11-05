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
  - id: compose-s3
    type: file
    path: docker-compose.s3.yml
  - id: compose-minio
    type: file
    path: docker-compose.minio.yml
  - id: silo
    type: web
    url: https://github.com/pgsty/silo
  - id: silo-release-20260903
    type: web
    url: https://github.com/pgsty/silo/releases/tag/RELEASE.2026-09-03T13-18-01Z
  - id: compose-override-example
    type: file
    path: docker-compose.override.yml.example
  - id: install-sh
    type: file
    path: install.sh
---

Katalon's Compose surface is split into a base stack, a development override, a production override, a Cantaloupe override, an optional S3 storage override with a dev-only MinIO companion, and a local customization example. The base stack defines the service graph for PostgreSQL/PostGIS, Redis, Elasticsearch, Cantaloupe, FastAPI, Celery workers, two Vite-built frontends, nginx, and backups; the overrides change exposure, rebuild behavior, TLS/routing, storage backends, and instance-specific settings without replacing the base service model [@compose-base] [@compose-dev] [@compose-prod].

The documented engine surface is Docker Compose. The manual installer requires `docker`, then selects `docker compose` or the legacy `docker-compose` binary for stack operations [@install-sh]. The Compose files may be useful evidence when evaluating Podman compatibility, but this repo does not define a Podman-specific profile or verified Podman run path [@compose-base] [@compose-dev] [@compose-prod].

## Base Stack

`docker-compose.yml` is the normal stack described by the [System Overview](../../architecture/system/system-overview). It defines:

| Service | Image or build | Main role | External port in base stack | Health check |
| --- | --- | --- | --- | --- |
| `db` | `postgis/postgis:16-3.4` | PostgreSQL 16 with PostGIS, backed by `db_data` | none | `pg_isready` |
| `redis` | `redis:7-alpine` | broker/cache dependency for async work | none | `redis-cli ping` |
| `elasticsearch` | Elasticsearch 8.13.4 | single-node search index | none | cluster health over `localhost:9200` |
| `cantaloupe` | `islandora/cantaloupe:7.0.22` | IIIF Image API service over mounted media | none | `curl` against `/iiif/3` |
| `api` | `docker/Dockerfile.backend` | FastAPI application | none (reachable only via nginx or `api:8000` on the Compose network) | `curl` against `/health` |
| `worker` | `docker/Dockerfile.worker` | Celery worker process | none | none |
| `beat` | `docker/Dockerfile.worker` | Celery beat scheduler | none | none |
| `admin` | `docker/Dockerfile.admin` | built Admin frontend served by nginx-in-container | `3000:80` | `wget` against `/index.html` |
| `portal` | `docker/Dockerfile.portal` | built Portal frontend served by nginx-in-container | `3001:80` | `wget` against `/index.html` |
| `nginx` | `nginx:alpine` | outer nginx container using `docker/nginx.conf`, also mounting `docker/certs/` | `80:80`, `443:443` | none |
| `backup` | `postgis/postgis:16-3.4` | scheduled database/media backup runner | none | none |

The base stack keeps database and Elasticsearch state in named volumes `db_data` and `es_data` (plus `cantaloupe_cache` for IIIF derivatives); media is bind-mounted from `${MEDIA_ROOT:-/srv/katalon/media}` into the API, worker, Cantaloupe, and backup services [@compose-base]. Cantaloupe uses `Java2dProcessor` for JPEG rendering, avoiding empty image responses from the TurboJPEG path on the supported image. Its derivative cache lives on disk (named volume `cantaloupe_cache` at `/data`, or `CANTALOUPE_CACHE_DIR`) so thumbnails survive restarts; the one-shot `cantaloupe-cache-init` service fixes ownership for the image's `cantaloupe` user first, Cantaloupe's cache worker deletes derivatives older than `CANTALOUPE_CACHE_SERVER_DERIVATIVE_TTL_SECONDS` (default 30 days), and `CANTALOUPE_FILESYSTEMCACHE_PATHNAME=/tmpfs/cache` selects a RAM-only tmpfs (`CANTALOUPE_CACHE_TMPFS_SIZE`) for small hosts. The Cantaloupe health check both fetches `/iiif/3` and verifies that the `cantaloupe` user can create and remove a file below the configured cache path [@compose-base]. This makes cache writability part of service readiness instead of discovering a root-owned cache only when image bytes come back empty. The backend images copy the pinned `uv` binary from `ghcr.io/astral-sh/uv:0.12.4` and use a BuildKit cache at `/root/.cache/uv`, so dependency downloads survive invalidated project-install layers without becoming image contents [@compose-base]. The backup service also mounts `docker/backup.sh` read-only and writes to `${BACKUP_ROOT:-/srv/katalon/backups}` [@compose-base].

## Dependency Edges

The API waits for healthy `db`, `redis`, and `cantaloupe`; the worker and beat wait for the same services; Admin and Portal wait for healthy API; outer nginx waits for healthy API, Admin, and Portal [@compose-base]. In the development override, API and worker also wait for healthy Elasticsearch, and Cantaloupe is allowed with `service_started` rather than its base health condition [@compose-dev].

## Development Override

`docker-compose.dev.yml` exposes infrastructure and switches API and frontend services to development images and bind mounts. It publishes PostgreSQL on `5432`, Redis on `6379`, Elasticsearch on `9200`, Cantaloupe on `8182`, API on `8000`, Admin on `4000`, and Portal on `4001` [@compose-dev].

The development API uses `docker/Dockerfile.backend.dev`, bind-mounts `backend/src` and `backend/migrations`, and runs `uvicorn katalon.main:app --reload` [@compose-dev]. The development worker bind-mounts `backend/src` and runs its Celery command through `watchfiles --filter python`, so it reloads automatically on Python file changes instead of requiring a manual `docker compose restart worker` [@compose-dev]. The development Admin and Portal use their separate frontend directories as build contexts, mount source directories plus anonymous `node_modules` volumes, and proxy API requests through `API_PROXY_TARGET=http://api:8000` [@compose-dev].

## Production Override

`docker-compose.prod.yml` is the production override used by the [Production Deployment](../../guides/operations/production-deployment) guide. It sets restart policies, memory limits, explicit environment variables, TLS nginx config, and `80`/`443` publication on nginx [@compose-prod]. It removes direct published ports from `api`, `admin`, and `portal` with `ports: !reset []`, so production access goes through nginx [@compose-prod].

Production Elasticsearch uses a fixed `ES_JAVA_OPTS=-Xms1g -Xmx1g` and a `2g` memory limit; the API, worker, Cantaloupe, database, Redis, and nginx each get smaller service-specific limits [@compose-prod]. The production nginx mounts `docker/nginx.prod.conf` and `docker/certs/` read-only [@compose-prod]. The base stack's outer nginx also mounts `docker/certs/` now, for a self-signed local HTTPS cert (`make certs`) rather than a production one — same mount point, different cert source [@compose-base].

## IIIF Override

`docker-compose.cantaloupe.yml` is a narrow IIIF override. It forces filesystem lookup settings, sets Cantaloupe's public base URI to `http://localhost`, and points API and worker at Cantaloupe internally on `http://cantaloupe:8182`; public manifests use nginx's `http://localhost/iiif/...` route [@compose-cantaloupe].

## S3 Storage Overrides

`docker-compose.s3.yml` activates the opt-in S3 media backend on top of any stack. It switches Cantaloupe to `S3Source` (basic lookup against the configured bucket) and passes `STORAGE_BACKEND=s3` plus the `S3_*` variables through to API and worker, failing fast with a clear message when bucket or credentials are missing. It deliberately keeps the `MEDIA_ROOT` mounts: logos and portal themes remain local files, only managed media objects move to the bucket. Because Cantaloupe 5.0.x S3Source always uses virtual-hosted addressing, `<bucket>.<endpoint-host>` must resolve in the deployment (wildcard DNS on the gateway); the backend side speaks path-style and needs no DNS preparation [@compose-s3].

`docker-compose.minio.yml` is the dev-only companion that adds a local MinIO service (console on `9001`) plus the same S3 wiring pointed at `http://minio:9000`, so the whole S3 path — upload, pyramid generation, IIIF reads — is testable without a cloud account. It gives the MinIO service a per-bucket Compose network alias so Cantaloupe's virtual-hosted lookups resolve locally. The bucket must be created once (MinIO console or any S3 client); nothing in the stack creates it automatically [@compose-minio].

### Local S3 Provider Lifecycle

MinIO remains the implemented companion. Silo is a compatible MinIO fork and the preferred eventual replacement because it preserves the S3 protocol, MinIO configuration variables, and on-disk format while shipping an arm64 container image [@silo]. Katalon must not switch yet: the latest published Silo server release documents that advisory SN-2026-011 affects it, with the fix only on the unreleased main branch [@silo-release-20260903]. After a published release includes that fix, replace MinIO only in this optional dev override, pin the image by digest, and exercise upload, pyramid generation, and Cantaloupe IIIF reads; the base and production Compose stacks remain S3-provider-neutral.

## Instance Override

`docker-compose.override.yml.example` documents local instance customization through Docker Compose's automatic override merge. Its examples change nginx's HTTPS port, add an API environment variable, and replace the database storage path with a host mount [@compose-override-example].
