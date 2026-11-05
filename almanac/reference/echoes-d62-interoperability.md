---
title: "ECHOES D6.2 Interoperability Assessment"
summary: "A deployed Katalon instance would likely qualify as an ECHOES CH-Cloud Level 1 provider and partially meet Level 2 on the semantic side (JSON-LD/CIDOC-CRM export, authority-source integration, OpenAPI); federated AAI, a machine-readable API error/versioning contract, SHACL validation, and URI lifecycle policy keep it from reaching full Level 2 or Level 3."
topics: [reference, integrations, api, operations, rdf, sparql]
sources:
  - id: echoes-d62
    type: web
    url: https://doi.org/10.5281/zenodo.18656368
  - id: main
    type: file
    path: backend/src/katalon/main.py
  - id: jsonld-format
    type: file
    path: backend/src/katalon/integrations/jsonld_format.py
  - id: rdf-service
    type: file
    path: backend/src/katalon/services/rdf_service.py
  - id: sparql-api
    type: file
    path: backend/src/katalon/api/v1/sparql.py
  - id: oxigraph
    type: file
    path: backend/src/katalon/integrations/oxigraph.py
  - id: sparql-admin
    type: file
    path: frontend/admin/src/components/screens/ScreenSparql.tsx
  - id: admin-routes
    type: file
    path: almanac/reference/frontend/admin-routes.md
  - id: subsystem-extension
    type: file
    path: almanac/decisions/platform/subsystem-extensions-vs-plugin-architecture.md
  - id: oai-and-export
    type: file
    path: almanac/architecture/workflows/oai-and-export-mappings.md
  - id: authority-sources
    type: file
    path: almanac/concepts/integrations/authority-sources.md
  - id: authority-service
    type: file
    path: backend/src/katalon/services/authority_service.py
  - id: pid-service
    type: file
    path: backend/src/katalon/services/pid_service.py
  - id: ark-adapter
    type: file
    path: backend/src/katalon/integrations/ark_adapter.py
  - id: dnb-urn-adapter
    type: file
    path: backend/src/katalon/integrations/dnb_urn_adapter.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: audit-service
    type: file
    path: backend/src/katalon/services/audit_service.py
  - id: auth-api
    type: file
    path: backend/src/katalon/api/v1/auth.py
  - id: cantaloupe
    type: file
    path: backend/src/katalon/integrations/cantaloupe.py
  - id: oaipmh-service
    type: file
    path: backend/src/katalon/services/oaipmh_service.py
  - id: limiter
    type: file
    path: backend/src/katalon/core/limiter.py
  - id: issue-268
    type: web
    url: https://github.com/karkraeg/Katalon/issues/268
---

ECHOES D6.2 ("Interoperability Requirements and Guidelines," European Cloud for Heritage Open Science, DOI [10.5281/zenodo.18656368](https://doi.org/10.5281/zenodo.18656368)) defines onboarding requirements for providers — datasets, APIs, applications, workflows, and semantic artefacts — joining the ECCCH federation, structured into three cumulative interoperability levels (L1 Basic, L2 Intermediate, L3 Advanced) [@echoes-d62]. This page records where a deployed Katalon instance would land against that catalogue if it were offered as a CH Cloud dataset/API provider, and which concrete gaps block a higher level. The assessment is a point-in-time comparison against an external standard, not a design decision made in this codebase; treat it as a lookup for future onboarding conversations, not as a roadmap commitment. Written 2026-09-05 and refreshed against the current RDF/SPARQL implementation: Katalon now has an optional first-party Oxigraph projection and read-only SPARQL endpoint, but the L3 blockers below remain [@sparql-api] [@oxigraph] [@subsystem-extension].

## Level 1 (Basic) — reachable with configuration

L1 requires machine-readable discovery metadata with a license/reuse statement, a stable identifier, and (if endpoints are exposed) TLS plus endpoint classification. Katalon's UUID primary keys are stable identifiers by construction [@models], and the schema-configurable `field_definitions` system can carry the required discovery fields (title, description, owner, contact) on any record type. Two fields are not built in and would need to be added per deployment: a dedicated license/rights field (see below) and a "responsible party / incident contact" field — both are configuration work, not missing capability.

## Level 2 (Intermediate) — strong semantics, blocked by AAI and operational contract

L2 adds structured semantics and operational readiness on top of L1.

**Where Katalon is already strong:**

- JSON-LD export mapping to CIDOC-CRM, LRMoo, SKOS, and DCTERMS exists for all seven record families via `JsonLdFormat` (OAI-PMH `metadataPrefix=json_ld`) and per-record `GET /api/v1/{record_type}/{id}/export?format=jsonld`/Turtle content negotiation via `rdf_service.py` [@jsonld-format] [@rdf-service] [@oai-and-export]. This satisfies REQ-META-006 (JSON-LD metadata) directly.
- The pluggable `AuthoritySource` registry (GND, GND-person, GND-subject, GeoNames, VIAF, Wikidata, Getty TGN, Getty AAT, ICONCLASS) gives controlled-vocabulary fields externally dereferenceable URIs, covering REQ-SEM-001/002 [@authority-service] [@authority-sources].
- FastAPI auto-generates an OpenAPI 3.x contract (`/api/openapi.json`), satisfying REQ-API-002 structurally.
- IIIF (Cantaloupe, Image/Presentation API v3) and OAI-PMH (with resumption tokens and OAI-DC/LIDO/METS-MODS formats) are both implemented [@cantaloupe] [@oaipmh-service] — both protocols D6.2 §2.2 names as CH-domain state of the art.

**Where L2 is blocked or incomplete:**

- **Federated AAI (SEC-04, level-gating for any restricted resource).** D6.2 requires OIDC/EGI-Check-in-style federated authentication for restricted resources at L2+. Katalon has JWT username/password login plus a separate API-key mechanism for machine access [@auth-api], but no OIDC/SAML/EGI Check-in integration anywhere in the codebase. Treating this as out of scope for a self-hosted, single-institution MMS is a legitimate product boundary, but it means a Katalon instance cannot claim L2 for any access-restricted resource — only for fully public records.
- **API versioning/deprecation policy (REQ-API-013/014/015).** All routers mount under a single `/v1` prefix [@main]; there is no version-negotiation mechanism, no `/version` endpoint, and no documented deprecation policy beyond an informal "Breaking" section in `CHANGELOG.md`.
- **Machine-readable error model (REQ-API-007).** API errors use FastAPI's default `{"detail": ...}` shape, not a documented, structured error object.
- **Structured monitoring/observability (REQ-MON-004/013).** `GET /health` checks Postgres, Elasticsearch, Redis, Cantaloupe, optional Oxigraph, and a Celery Beat/Worker heartbeat and returns 503 on failed readiness checks, but there is no separate `/ready`, no metrics endpoint, no structured JSON logging, and no request-correlation IDs [@main].
- **Contract drift detection (REQ-MON-009).** No CI step diffs the OpenAPI contract across releases. *(Note: a checked-in `openapi.json` with a `--check` pre-commit hook now exists, which catches local drift before commit, but there is still no CI job diffing it release-to-release.)*

## Level 3 (Advanced) — not reached

L3 requires RDF representations validated against SHACL shapes, URI stability/deprecation discipline, and, when linked data is exposed through an API, a SPARQL endpoint with declared limits.

- RDF/Turtle output exists (`rdf_service.py`), but no SHACL shapes or validation pipeline exist for it.
- Katalon now exposes a read-only SPARQL 1.1 endpoint at `/sparql` and `/v1/sparql` when `oxigraph_enabled` and `sparql_endpoint_enabled` are true. The endpoint accepts GET and POST query forms, validates queries as read-only, applies the configured query timeout and rate limit, and requires JWT or API-key authentication unless `sparql_require_auth` is disabled [@sparql-api]. The Admin `#sparql` route is a feature-gated query-builder surface with saved queries and NL2SPARQL assistance, but it is not itself the public interoperability contract [@sparql-admin] [@admin-routes].
- PID minting (`pid_service.py`, ARK via `ark_adapter.py`, DNB URN via `dnb_urn_adapter.py`) checks for collisions before assignment [@pid-service] [@ark-adapter] [@dnb-urn-adapter], but nothing enforces immutability of an already-minted PID against later record edits, and there is no formal deprecation/redirect mechanism for changed URIs.
- No semantic drift monitoring exists.

`AuditLog` and `RecordSnapshot` already give Katalon a provenance/versioning substrate (who/when/what changed, full JSONB snapshots) [@models] [@audit-service] that L2/L3 provenance requirements (REQ-PROV-*) could build on without new data-model work.

## License Field Caveat

A license/rights field is trivial to add via `field_definitions` — media records already carry one (license/Rechteinhaber, per `CHANGELOG.md`). D6.2's REQ-META-002 wants the license expressed machine-readably, though: a plain free-text field does not satisfy that, only a controlled-vocabulary/URI-typed field (a Creative Commons or RightsStatements.org URI) does. This is a documentation/best-practice gap for schema authors, not a code gap — see the tracked follow-up below.

## Tracked Follow-Up

Concrete work items opened against the [Export & Interoperability roadmap](project-roadmap) (#263):

- [#358](https://github.com/karkraeg/Katalon/issues/358) — SPARQL endpoint for RDF data (extends the RDF/Turtle export already in `rdf_service.py`) — covered by the optional read-only `/sparql` endpoint and Admin query builder in current code; re-check the issue's own acceptance criteria before closing.
- [#359](https://github.com/karkraeg/Katalon/issues/359) — SHACL validation for the RDF/JSON-LD export
- [#360](https://github.com/karkraeg/Katalon/issues/360) — public-docs guidance on using a controlled-vocabulary/URI field type for license/rights, not free text

These narrow the open question already on file in [#268](https://github.com/karkraeg/Katalon/issues/268) ("Graph-Ansicht + RDF-Ausgabe," still idea-stage) into concrete, scoped sub-issues [@issue-268]. Rate limiting (`slowapi`, per-endpoint overrides) and CORS configuration already exist [@limiter] and are not gaps against D6.2's baseline security requirements.
