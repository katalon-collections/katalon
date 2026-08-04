---
title: "Katalon Domain Model"
summary: "Katalon's domain model defines a GLAM metadata system with configurable records, relations, media, search, and separate public and admin surfaces."
topics: [concepts, domain, metadata, architecture]
sources:
  - id: readme
    type: file
    path: README.md
  - id: concept
    type: file
    path: KONZEPT.md
  - id: product
    type: file
    path: PRODUCT.md
  - id: architecture-doc
    type: file
    path: docs/00_architektur.md
---

Katalon is a GLAM metadata management system for institutions that need configurable collection records rather than a fixed library or repository schema. It takes the configurable metadata idea associated with CollectiveAccess and reworks it as a Python and React system with a REST API, two frontends, PostgreSQL/PostGIS storage, Elasticsearch search, and IIIF media delivery [@concept]. The rest of the wiki uses this page as the domain frame for [Primary Record Types](primary-record-types), [System Overview](../../architecture/system/system-overview), and the [Technology Stack](../../decisions/platform/technology-stack).

## What Katalon Models

Katalon models collection knowledge for galleries, libraries, archives, and museums. Its core records describe objects, people and organizations, places, works, events, concepts, and institutional processes around objects [@concept]. The product goal is not to hide specialist cataloging work; it is to let staff define, maintain, search, and publish complex collection data without changing application code for every metadata schema change [@product].

The system is explicitly not a classic library system and does not adopt MARC, copy circulation, or Z39.50 as its model. It is also not an institutional repository centered on deposit workflows, embargoes, and DOI minting [@concept]. That boundary keeps the domain vocabulary focused on collection objects and the contextual records around them.

## CollectiveAccess Lineage

CollectiveAccess is the main product ancestor in the repository documentation. Katalon keeps the useful part: configuration over coding for heterogeneous collection metadata [@readme]. It rejects the parts that make CollectiveAccess hard to maintain in this project context: monolithic PHP, XML-heavy configuration, and missing modern API and Python integration [@concept].

That lineage explains why Katalon has a broad record vocabulary instead of one generic item table. The domain needs physical or digital artefacts, actors, places, and abstract events or works to remain distinct enough for users and queries, while still allowing configurable fields and relations across them [@concept].

## Headless Shape

The domain model is exposed through an API-first architecture. A FastAPI backend owns REST endpoints and persistence, while the Admin frontend handles protected cataloging workflows and the Portal frontend handles public discovery [@architecture-doc]. This split lets the same domain records support back-office editing and public access without coupling the two user experiences.

PostgreSQL stores the current record state, including JSONB metadata and PostGIS geometry for places; Elasticsearch provides full-text and faceted discovery; Cantaloupe and IIIF expose image media for deep zoom viewing [@readme]. These technologies are implementation details, but they matter to the domain because they make configurable metadata, geographic places, public search, and image inspection first-class behaviors.

## Product Vocabulary

The central vocabulary starts with the four inventory-facing primary record types: Object, Entity, Place, and Occurrence. Procedures are separate records for processes such as loans, acquisition, and conservation [@concept]. Follow [Primary Record Types](primary-record-types) for the detailed distinctions, and [Procedures](procedures) for the process model.

Katalon treats metadata definitions as institution-specific. Field labels, repeatability, requiredness, field types, and subtype-specific fields are configuration data rather than source-code changes [@readme]. That is the bridge between the domain model and the schema engine: the fixed record families provide stable system behavior, while configurable fields let each institution describe its own material.
