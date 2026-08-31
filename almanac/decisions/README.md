---
title: "Decisions"
summary: "Index of durable Katalon architecture decisions grouped by the system area they constrain."
topics: [decisions, architecture, orientation]
---

Katalon's decision pages record choices that future changes must account for before changing data shape, routing, workflows, deployment behavior, search indexing, or importer scope. Use this index when a task sounds like a design question rather than a small code fix.

## Platform And Data Shape

[Technology Stack](platform/technology-stack) records the fixed Python/FastAPI, PostgreSQL/PostGIS, Elasticsearch, Cantaloupe, Celery/Redis, React/Vite, and Docker Compose stack.

[Separate Record Tables](data/separate-record-tables) explains why Objects, Entities, Places, and Occurrences are separate persisted record families. [Generic Relation Model](data/generic-relation-model) explains why cross-record links use one generic relation table with relation metadata.

## Metadata And Search

[Vocabulary Term Custom Fields](metadata/vocabulary-term-custom-fields) covers configurable metadata on vocabulary terms. [Multilingual Content](metadata/multilingual-content) covers the lang-keyed dict model for labels and translatable values, the `supported_languages` config, and the dependency-free portal i18n. [Inherited Fields In Elasticsearch](search/inherited-fields-in-elasticsearch) covers relation-derived search fields and denormalized Elasticsearch documents.

[Advanced Relational Search](search/advanced-relational-search) records why nested relation conditions are resolved inside-out at query time rather than denormalized recursively.

[Schema Configured Portal Facets](frontend/schema-configured-portal-facets) explains why public Portal facets come from schema configuration rather than hard-coded frontend filters.

## Frontend And Workflow Behavior

[Admin Hash Routing](frontend/admin-hash-routing) records the Admin routing choice. [Optimistic Locking](workflows/optimistic-locking) records the concurrency contract for record and procedure saves.

## Importer Scope

[Multi-Format Importer](importer/multi-format-importer) records the importer shape across CSV, Excel, and XML. [XML Importer Scope](importer/xml-importer-scope) records the XML parser boundary. [Fuzzy Vocabulary Clustering](importer/fuzzy-vocabulary-clustering) records the dry-run reconciliation approach for near-duplicate controlled terms.

## Operations

[Deep Health Check](operations/deep-health-check) records why `/health` checks database and Elasticsearch in one Docker Compose readiness endpoint. [Broker Tolerant Enqueue](operations/broker-tolerant-enqueue) records why task enqueue failures should not break core writes when Redis is unavailable. [Docker Customization Strategy](operations/docker-customization-strategy) records how instance-specific compose and deployment customization stays out of the base stack. [Cantaloupe Auth Gate](operations/cantaloupe-auth-gate) records why nginx must authorize `/iiif/` derivatives through the backend before proxying to Cantaloupe. [katalon-cli Distribution](operations/katalon-cli-distribution) records why production installs use a separate CLI pulling pinned release images instead of a source-repo checkout.
