---
title: "Getting Started"
summary: "Entry point for the Katalon wiki and the main reading paths for future agents."
topics: [orientation, domain, operations]
sources:
  - id: readme
    type: file
    path: README.md
  - id: agents
    type: file
    path: AGENTS.md
  - id: concept
    type: file
    path: KONZEPT.md
---

Katalon is an open-source metadata management system for GLAM collections. The product combines configurable collection metadata, controlled vocabularies, cross-record relations, media and IIIF delivery, full-text search, and separate Admin and Portal frontends [@readme]. This wiki is the durable map for future coding agents: start here for the domain model, then follow the architecture, workflow, guide, and reference pages that match the task.

## First Reading Path

Read [Katalon Domain Model](concepts/domain/katalon-domain-model) first when the task involves product meaning, record vocabulary, or CollectiveAccess comparisons. Katalon is built around configurable metadata for collection objects, people or organizations, places, and occurrences, with Procedures as a separate process type for loans, acquisition, and conservation [@concept].

Read [System Overview](architecture/system/system-overview) next when the task touches runtime shape. The deployed system uses a FastAPI backend, PostgreSQL/PostGIS, Elasticsearch, Redis and Celery, Cantaloupe, nginx, and two React/Vite frontends [@readme].

Read [Local Workflows](guides/development/local-workflows) before running development commands. Backend Python commands are expected to run from `backend/`, and the root virtual environment can use the wrong interpreter for backend tests [@agents].

Read [Ports And Routing](reference/operations/ports-and-routing) before browser checks. The normal production-like Compose stack routes Admin at `http://localhost/admin/` and Portal at `http://localhost/`; direct container ports are for debugging and can show a blank shell when base paths do not match [@agents].

## Domain Cluster

The domain pages explain the record vocabulary that most backend, frontend, import, search, and export code uses. [Primary Record Types](concepts/domain/primary-record-types) explains Objects, Entities, Places, Occurrences, and Procedures. [Procedures](concepts/domain/procedures) explains why process records are separate from inventory records and how object loan invariants work.

## Runtime Workflow Cluster

Use the workflow pages when a task crosses API routes, services, workers, and frontends. [Record CRUD And Publishing](architecture/workflows/record-crud-and-publishing) is the safest entry point for primary-record lifecycle work, and [Schema Driven Record Forms](architecture/workflows/schema-driven-record-forms) connects that backend shape to Admin form behavior.

Read [Importer Pipeline](architecture/workflows/importer-pipeline) for CSV, Excel, XML, dry-run, vocabulary reconciliation, and Celery-backed import work. Read [Media And IIIF](architecture/workflows/media-and-iiif) for object media uploads, batch media import, Cantaloupe processing, and portal IIIF viewing. Read [Search And Indexing](architecture/workflows/search-and-indexing) before changing Elasticsearch document construction, visibility filters, relation denormalization, or reindex repair paths.

Read [Authority Sources](concepts/integrations/authority-sources) before changing authority adapters or authority-backed fields, and read [OAI And Export Mappings](architecture/workflows/oai-and-export-mappings) before changing OAI-PMH output or metadata export mappings.

## Frontend And Public Access

For Admin tasks, pair [Admin Shell And API Client](architecture/frontend/admin-shell-and-api-client) with [Admin Routes](reference/frontend/admin-routes). For Portal tasks, pair [Portal Routing And Theming](architecture/frontend/portal-routing-and-theming), [Portal Search And Facets](architecture/workflows/portal-search-and-facets), and [Portal Routes](reference/frontend/portal-routes).

## Work Safely

Treat current code as runtime truth, and use ordinary repository documentation as intent unless it agrees with code. This matters in Katalon because the concept document describes the long-lived product model while the SQLAlchemy models and API routers define current behavior [@concept].

Never delete database volumes or run destructive Compose volume commands without explicit approval. The project instructions require log inspection and option presentation first because database volume deletion is irreversible [@agents].

For production work, read [Production Deployment](guides/operations/production-deployment), [Admin Deploy Verification](guides/operations/admin-deploy-verification), [Environment And Secrets](reference/operations/environment-and-secrets), and [Known Gotchas](reference/operations/known-gotchas) before changing compose, nginx, Vite base paths, startup settings, or data recovery procedures.
