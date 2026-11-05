---
title: "Advanced Relational Search"
summary: "Advanced portal queries use typed index projections and bounded inside-out relation resolution instead of recursive denormalization."
topics: [decisions, search, elasticsearch, relations, portal]
sources:
  - id: advanced-search-service
    type: file
    path: backend/src/katalon/services/advanced_search_service.py
  - id: search-service
    type: file
    path: backend/src/katalon/services/search_service.py
  - id: inherited-decision
    type: file
    path: almanac/decisions/search/inherited-fields-in-elasticsearch.md
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/advanced-relational-search.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/advanced-relational-search.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


## Context

Portal users need queries such as Objects linked to photographers born before 1950 whose birth place is Bremen. Recursively embedding all linked metadata would multiply index data and require multi-hop reindex cascades [@inherited-decision].

## Decision

Each document stores typed values only for its own public searchable fields and target IDs for its own schema relation fields. Advanced relation groups are resolved from the innermost target outwards. The result type is fixed per query, relation depth is limited to two steps, and each intermediate ID set is limited to 10,000 [@advanced-search-service] [@search-service].

## Consequences

Changes to linked records require only their normal indexing, not recursive parent reindexing. The query service performs additional Elasticsearch requests for relation steps. Users must narrow a condition when an intermediate result exceeds the bound.
