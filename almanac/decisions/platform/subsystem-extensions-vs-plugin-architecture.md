---
title: "Subsystem Extensions vs. Plugin Architecture"
summary: "Deep infrastructure extensions like Oxigraph and SPARQL are implemented as first-party modules with feature flags and Docker Compose profiles, rejecting a generic dynamic plugin system as YAGNI."
topics: [decisions, architecture, platform, rdf, sparql, plugins]
sources:
  - id: issue-364
    type: issue
    number: 364
  - id: issue-358
    type: issue
    number: 358
  - id: issue-359
    type: issue
    number: 359
  - id: technology-stack
    type: file
    path: almanac/decisions/platform/technology-stack.md
  - id: docker-customization
    type: file
    path: almanac/decisions/operations/docker-customization-strategy.md
  - id: elasticsearch-integration
    type: file
    path: backend/src/katalon/integrations/elasticsearch.py
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/subsystem-extensions-vs-plugin-architecture.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/subsystem-extensions-vs-plugin-architecture.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Major platform capabilities that span multiple infrastructure layers—such as the Oxigraph triple store projection (#364) and the read-only SPARQL endpoint (#358)—are implemented as optional first-party modules within the core codebase, governed by configuration flags and Docker Compose profiles. A dynamic, third-party plugin lifecycle framework is rejected as unnecessary complexity and YAGNI.

## Context

GitHub Issues #364 (Materialized RDF Projection in Oxigraph), #358 (Authorized Read-Only SPARQL Endpoint), and #359 (RDF Contract Tests and SHACL Validation) outline a substantial Linked Data expansion for Katalon [@issue-364] [@issue-358] [@issue-359]:
1. An optional, materialized graph database (Oxigraph) syncing continuously from PostgreSQL.
2. Background synchronization workers hooked into record mutations, vocabulary changes, and schema updates.
3. A read-only SPARQL query endpoint with dedicated authentication, query timeouts, and rate limits.
4. Monitoring, sync-lag diagnostics, and full rebuild triggers in the administration UI.

Because these capabilities are optional and not every GLAM institution requires a triple store or SPARQL endpoint, the question arose whether Katalon should build a generic plugin architecture or dynamic extension system to host them.

Katalon already has two distinct customization and extension mechanisms:
- **Focused Strategy Adapters:** Specific, isolated extension points (`AuthoritySource` for authority lookup, `MetadataFormat` for OAI-PMH/export formats, `SourceFormat` for import parsing) use an abstract base class and an in-memory or database-backed registry. These adapters have a narrow contract (input in, output out), require no database schema changes, and do not introduce background daemons.
- **Operational & Theme Customization:** Institutional branding and portal visual customizations use mounted theme packages (`theme.json` + CSS) and Docker Compose override files (`docker-compose.override.yml`), avoiding downstream image rebuilds [@docker-customization].

## Decision

**Reject a generic dynamic plugin framework for subsystem-level extensions.** Major extensions like Oxigraph and SPARQL are built as standard first-party modules inside the core repository, managed via feature toggles and Docker Compose profiles:

1. **Subsystems are not plugins:** A feature like Oxigraph/SPARQL cuts across the entire architectural stack:
   - *Infrastructure:* Dedicated daemon container with persistent storage volumes.
   - *Workers:* Celery sync tasks wired into primary record save, delete, publication, and cascade events.
   - *API & Routing:* FastAPI routes requiring middleware, rate limiting, and auth dependencies.
   - *Observability:* Admin UI views reporting sync status, lag, and triggering bulk rebuilds.
   - *Configuration:* Core settings in Pydantic models.
   Attempting to abstract these touchpoints behind a dynamic plugin lifecycle framework (runtime dynamic routing, dynamic Celery worker registration, dynamic migration management, UI component injection) would create a massive meta-framework on top of FastAPI, Celery, and Vite without tangible benefit.

2. **Precedent in the Core Platform:** The architectural role model already exists in Katalon's core stack [@technology-stack]:
   - *Elasticsearch* provides search indexing, cluster health checks, and Celery reconciliation tasks (`index_tasks.py`), backed by an optional or configurable external service [@elasticsearch-integration].
   - *Cantaloupe* provides IIIF image derivative generation, authenticated proxying, and pyramid generation tasks.
   Neither Elasticsearch nor Cantaloupe is a "plugin"; they are tightly integrated, first-party platform integrations. Oxigraph follows this identical pattern as a materialized read-projection (CQRS) beside PostgreSQL.

3. **Opt-in Deployment without Overhead:**
   - **Code isolation:** The code lives statically in `katalon.integrations.oxigraph`, `katalon.services.rdf_sync_service`, and `katalon.api.v1.sparql`, covered by standard type checks and CI test suites.
   - **Feature Toggle:** Controlled via configuration (e.g. `OXIGRAPH_ENABLED=false` by default). When disabled, Celery synchronization tasks short-circuit immediately with a zero-overhead `return`, and SPARQL routes return 404/501 or are unmounted.
   - **Compose Profiles:** The Oxigraph service is defined in Docker Compose under an optional profile (`profiles: ["rdf"]`). Default deployments do not launch the container, consuming 0 MB memory and opening no ports. Institutions wanting RDF enable the profile via environment (`COMPOSE_PROFILES=rdf`) or `katalon-cli`.

## Consequences

- **Developer Simplicity:** Contributors work with standard Python/FastAPI and React code. There is no plugin SDK, no custom packaging format, and no isolated classloader or runtime sandboxing to maintain.
- **Zero Runtime Tax for Non-Users:** Installations that do not need SPARQL run the base compose stack without the Oxigraph container, and background event hooks exit immediately when the feature flag is disabled.
- **PostgreSQL Remains Source of Truth:** Oxigraph remains strictly a materialized secondary projection, exactly as Elasticsearch is for search text. Rebuilding the graph from PostgreSQL is possible at any time.
- **Adapter Pattern Remains Restricted to Pure Callbacks:** The existing adapter/registry pattern (`AuthoritySource`, `MetadataFormat`) remains reserved for narrow, stateless strategies with fixed request-response contracts.
