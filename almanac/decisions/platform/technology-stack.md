---
title: "Technology Stack"
summary: "Katalon's stack fixes FastAPI, PostgreSQL/PostGIS, Elasticsearch, Celery/Redis, Cantaloupe, React/Vite, and Docker Compose as one deployment-oriented platform choice."
topics: [decisions, architecture, platform, deployment, search, media]
sources:
  - id: agents
    type: file
    path: AGENTS.md
  - id: decision
    type: file
    path: .agents/knowledge/decisions/tech-stack.md
  - id: readme
    type: file
    path: README.md
  - id: architecture-doc
    type: file
    path: docs/00_architektur.md
  - id: compose
    type: file
    path: docker-compose.yml
---

Katalon uses a fixed platform stack instead of selecting infrastructure per feature. The recorded decision sets Python 3.12 and FastAPI for the backend, PostgreSQL 16 with PostGIS and JSONB for storage, Elasticsearch 8 for search, Cantaloupe for IIIF images, Celery with Redis for background work, two React/Vite frontends, and Docker Compose for deployment [@decision]. This stack supports Katalon's [domain model](../../concepts/domain/katalon-domain-model): GLAM records need dynamic metadata, place geometry, public search, media delivery, and a separate admin surface.

## Context

Katalon is a Python and React metadata management system for GLAM collections. The project context sets its design goals: schema configuration through the UI instead of config files, a clean API for modern frontends, and native Python/data-science integration [@agents]. The README repeats the same product direction and presents Katalon as an API-backed MMS with dynamic schemas, controlled vocabularies, entity relations, IIIF, search, and theming [@readme].

The stack decision was made as a package at project start, not as a series of unrelated component decisions [@decision]. That matters because each choice constrains the others. Dynamic fields need JSONB storage, places need PostGIS, rich public discovery needs Elasticsearch, media delivery needs IIIF infrastructure, and two different user surfaces need separate frontends.

## Decision

The backend is FastAPI on Python 3.12, exposed as REST plus OAI-PMH according to the architecture documentation [@architecture-doc]. The Compose file builds the `api`, `worker`, and `beat` services from the backend Dockerfiles and passes database, Redis, Elasticsearch, Cantaloupe, media, secret, and base URL settings through environment variables [@compose].

PostgreSQL with PostGIS is the primary datastore. The Compose stack uses the `postgis/postgis:16-3.4` image for `db`, persists it in `db_data`, and checks readiness with `pg_isready` [@compose]. The data model uses JSONB metadata for configurable fields and PostGIS geometry for places, which is why this decision is coupled to [separate record tables](../data/separate-record-tables) [@architecture-doc].

Elasticsearch 8 is the search service, Redis is the broker/backend for Celery work, and Cantaloupe is the IIIF Image API service [@architecture-doc]. The Compose stack makes those roles explicit with `elasticsearch`, `redis`, `worker`, `beat`, and `cantaloupe` services, including persistent `es_data` and a read-only media mount into Cantaloupe [@compose].

The frontend is two separate React/Vite applications: an authenticated Admin UI and a public Portal [@decision]. The architecture document describes Admin as the data-entry and management surface and Portal as the public search and IIIF surface [@architecture-doc]. The Compose stack builds and serves them as separate `admin` and `portal` containers behind nginx [@compose].

Deployment uses Docker Compose. The recorded reason is the target environment: GLAM institutions should be able to run the system without operating a Kubernetes-style platform [@decision]. The README's quickstart reflects that operational target by starting from Docker and Docker Compose v2, with `./install.sh --up` as the main path [@readme].

## Consequences

Feature work should assume the platform services exist and use them directly. Search belongs in Elasticsearch-backed indexing rather than ad hoc SQL full-text substitutes; media and deep zoom belong in the Cantaloupe/IIIF path; background jobs belong in Celery when work should not block API requests [@architecture-doc].

Persistence design should preserve the PostgreSQL/PostGIS/JSONB split. JSONB is the flexible metadata layer, but geometry is a real PostGIS column on places and record families remain typed tables [@architecture-doc]. This is why the stack decision connects to the [Schema Engine](../../concepts/metadata/schema-engine) and [Primary Record Types](../../concepts/domain/primary-record-types) rather than living only as deployment trivia.

The frontend split is also a constraint. Admin and Portal can share API concepts, but they are separate applications with different routing, authentication, and deployment behavior [@architecture-doc]. Work that changes public display does not automatically imply an Admin UI change, and work that changes cataloguing behavior usually does.
