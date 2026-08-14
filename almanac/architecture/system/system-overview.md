---
title: "System Overview"
summary: "Katalon runs as a Docker Compose system with a FastAPI backend, two React frontends, PostgreSQL/PostGIS, Elasticsearch, Redis/Celery, Cantaloupe, and nginx."
topics: [architecture, deployment, api, frontend, search, media]
sources:
  - id: compose
    type: file
    path: docker-compose.yml
  - id: nginx
    type: file
    path: docker/nginx.conf
  - id: app
    type: file
    path: backend/src/katalon/main.py
  - id: architecture-doc
    type: file
    path: docs/00_architektur.md
---

Katalon is an API-first metadata management system split into a FastAPI backend, two separate React frontends, and service dependencies for storage, search, queueing, and IIIF images. The deployed Compose stack contains PostgreSQL with PostGIS, Redis, Elasticsearch, Cantaloupe, the API, a Celery worker, a Celery beat process, Admin, Portal, nginx, and backup services, so most runtime behavior crosses container boundaries rather than living in one process [@compose]. The architecture document states the same product shape at intent level: a Python REST API consumed by separate Admin and Portal React applications [@architecture-doc].

## Runtime Boundary

The FastAPI process owns the HTTP API and mounts the authenticated working API under `/v1`, a separate anonymous Portal read model under `/portal/v1`, OAI-PMH outside those prefixes, and health checks at `/health` [@app]. This makes the backend the central coordination point: frontends call it, workers share its database models and settings, and health checks use it to report readiness.

The Compose stack keeps external concerns in separate services. PostgreSQL/PostGIS is the primary database, Elasticsearch stores search indexes, Redis is both Celery broker and result backend, and Cantaloupe reads the media directory as an image source [@compose]. The worker and beat services use the same backend image lineage and settings as the API, but run Celery commands instead of serving HTTP [@compose].

## Edge Routing

nginx is the public routing layer for the production-like stack. `/api/` is rewritten to the API without the `/api` prefix; `/v1/` and `/portal/v1/` are proxied to the API; `/iiif/` is proxied to Cantaloupe; `/admin/` is rewritten to the Admin container; and all remaining paths go to Portal [@nginx]. That routing explains why the user-facing system has one main origin even though Admin, Portal, API, and Cantaloupe are separate services.

This route split also fixes the boundary between frontend assets and backend data. Admin is served below `/admin/`, Portal owns `/`, and both reach backend endpoints through nginx rather than direct container ports [@nginx]. For exact operational port rules, use the ports and routing reference when available.

## Startup Dependencies

Compose health checks gate most service startup. The API waits for database, Redis, and Cantaloupe health, while nginx waits for API, Admin, and Portal health [@compose]. Elasticsearch has its own health check and is configured as a single-node, unauthenticated Elasticsearch 8 service in Compose [@compose].

FastAPI startup adds application-level checks and seed data on top of container readiness. The lifespan function creates default users, vocabularies, record subtypes, singleton config rows, authority sources, label fields, checks Cantaloupe, and then tries to ensure the Elasticsearch index [@app]. The Elasticsearch step is explicitly best-effort, while the Cantaloupe check raises during startup if the image server is unreachable [@app].

## Related Pages

Read [API Application Startup](../backend/api-application-startup) for the exact FastAPI lifespan sequence, and [Persistence Model](persistence-model) for the database model beneath the services.
