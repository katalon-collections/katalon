---
title: "Decisions"
summary: "Index of durable Katalon architecture decisions grouped by the system area they constrain."
topics: [decisions, architecture, orientation]
---

These pages summarize current constraints and implementation. Authoritative
rationale, alternatives and status live in `.agents/knowledge/decisions/`;
each summary declares and cites its corresponding OKF record. Change that
record first when changing a decision. Keep these routes stable for existing
links, and use architecture/workflow pages for detailed current behavior.

## Data

- [Generic Relation Model](data/generic-relation-model)
- [LRMoo / FRBR Mapping Onto Occurrence](data/lrmoo-frbr-occurrence-mapping)
- [Separate Record Tables](data/separate-record-tables)
- [Storage Locations](data/storage-locations)

## Metadata

- [Multilingual Content](metadata/multilingual-content)
- [Vocabulary Term Custom Fields](metadata/vocabulary-term-custom-fields)
- [File Field Attachments](metadata/file-field-attachments)

## Search

- [Advanced Relational Search](search/advanced-relational-search)
- [Inherited Fields In Elasticsearch](search/inherited-fields-in-elasticsearch)

## Frontend

- [Admin Hash Routing](frontend/admin-hash-routing)
- [Configurable Portal Homepage Blocks](frontend/configurable-portal-homepage)
- [Configurable Portal Terminology](frontend/configurable-portal-terminology)
- [Schema Configured Portal Facets](frontend/schema-configured-portal-facets)
- [Staff Portal Authentication](frontend/staff-portal-authentication)

## Workflows

- [Optimistic Locking](workflows/optimistic-locking)
- [Presence Lock](workflows/presence-lock)

## Importer

- [Fuzzy Vocabulary Clustering](importer/fuzzy-vocabulary-clustering)
- [JSON Import ist YAGNI](importer/json-import-yagni)
- [Multi-Format Importer](importer/multi-format-importer)
- [XML Importer Scope](importer/xml-importer-scope)

## Operations

- [Broker Tolerant Enqueue](operations/broker-tolerant-enqueue)
- [Cantaloupe Auth Gate](operations/cantaloupe-auth-gate)
- [Deep Health Check](operations/deep-health-check)
- [Docker Customization Strategy](operations/docker-customization-strategy)
- [katalon-cli Distribution](operations/katalon-cli-distribution)
- [License and External Branding](operations/license-and-branding)

## Platform

- [Auth Token Architecture](platform/auth-token-architecture)
- [Subsystem Extensions vs. Plugin Architecture](platform/subsystem-extensions-vs-plugin-architecture)
- [Technology Stack](platform/technology-stack)

## Preservation

- [BagIt Preservation Export](preservation/bagit-preservation-export)
