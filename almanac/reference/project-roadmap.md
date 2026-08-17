---
title: "Project Roadmap"
summary: "Lookup reference for the GitHub roadmap umbrella issues that define current Katalon work areas."
topics: [reference, roadmap, development]
sources:
  - id: release-ops
    type: web
    url: https://github.com/karkraeg/Katalon/issues/260
  - id: schema-search
    type: web
    url: https://github.com/karkraeg/Katalon/issues/261
  - id: import-migration
    type: web
    url: https://github.com/karkraeg/Katalon/issues/262
  - id: export-interop
    type: web
    url: https://github.com/karkraeg/Katalon/issues/263
  - id: admin-ux
    type: web
    url: https://github.com/karkraeg/Katalon/issues/264
  - id: portal-publication
    type: web
    url: https://github.com/karkraeg/Katalon/issues/265
  - id: media-preservation
    type: web
    url: https://github.com/karkraeg/Katalon/issues/266
  - id: collection-procedures
    type: web
    url: https://github.com/karkraeg/Katalon/issues/267
---

Katalon's active planning surface is the GitHub roadmap umbrella set, not a committed implementation-plan file. The umbrella issues group work by product and operational area, and each issue states that concrete work belongs in sub-issues [@release-ops] [@schema-search] [@import-migration] [@export-interop] [@admin-ux] [@portal-publication] [@media-preservation] [@collection-procedures]. Use this page as a routing reference before choosing an implementation area; use GitHub for the live sub-issue list and status.

## Umbrella Issues

| Issue | Area | Scope |
| --- | --- | --- |
| #260 | Release quality and operations | Testing reliability, CI, auth sessions, scalability, packaging, deployment, and operations documentation [@release-ops]. |
| #261 | Schema, search, and data integrity | Metadata-model consistency, relation behavior, Elasticsearch denormalization, subtypes, vocabularies, and data-integrity work [@schema-search]. |
| #262 | Import and data migration | Importer UX, preview and rollback questions, upsert diffs, larger uploads, jobs, and vocabulary import [@import-migration]. |
| #263 | Export and interoperability | Database export, LIDO, CSV, JSON, persistence formats, and external identifiers [@export-interop]. |
| #264 | Editorial Admin UX | Forms, batch editing, mobile use, microcopy, AI assistance, and personal work organization [@admin-ux]. |
| #265 | Portal and publication | Public discoverability, portal UX, multilingual presentation, SEO, analytics, publication cases, and public accounts [@portal-publication]. |
| #266 | Media and long-term availability | Annotations, large files, external storage, additional viewers, and preservation beyond the completed IIIF base [@media-preservation]. |
| #267 | Collection and procedure management | Procedures, structured procedure data, collections, and storage locations [@collection-procedures]. |

## Use In Planning

Before taking a broad feature or hardening task, pick the umbrella that owns the main product risk, then inspect its current sub-issues in GitHub. Do not treat this reference as a backlog snapshot; it records the durable routing map, while issue state and sub-issue membership can change.
