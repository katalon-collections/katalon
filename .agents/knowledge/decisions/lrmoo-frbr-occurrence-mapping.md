---
type: Decision
title: "LRMoo / FRBR Mapping Onto Occurrence"
tags: [architecture, documentation]
timestamp: 2026-10-30T00:00:00Z
origin: almanac/decisions/data/lrmoo-frbr-occurrence-mapping.md
consolidated: 2026-10-30
---

Katalon's Occurrence type already covers "Werke (FRBR), Ereignisse, Konzepte" in the recorded four-record-type decision [4]. This page records the design pattern for mapping IFLA's LRMoo (the CIDOC-CRM-compatible, event-based harmonization of LRM, successor to FRBRoo) and plain FRBR onto Katalon's existing primitives.

## Pattern

WEMI levels map onto existing record families and subtypes, not a new table:

- Work, Expression, Manifestation (F1–F3) → three `record_subtypes` under Occurrence (e.g. `work`, `expression`, `manifestation`), using the existing subtype-scoping mechanism [2].
- Item (F5) → **Object**, not Occurrence. An item is the concrete physical or digital exemplar, matching the existing split between abstract Occurrences and concrete Objects [1].
- The WEMI hierarchy itself (Work realized by Expression, Expression embodied by Manifestation, Manifestation exemplified by Item) → ordinary rows in the generic `relations` table with dedicated `relation_type` codes (e.g. `has_expression`, `has_manifestation`, `exemplifies`), no schema change required [3] [5].

LRMoo's creation events (F27 Work Creation, F28 Expression Creation, F30 Manifestation Creation, F32 Item Production) reify the act of creation as its own CRM-style event, with its own date, place, and one or more agents in a role. Two ways to carry that in Katalon:

1. **Event as relation metadata.** Put date/agent directly into the JSONB metadata of the WEMI-level relation. Simple, but only fits a single agent/role per link and gives the event no identity of its own.
2. **Event as its own Occurrence record.** A subtype such as `work_creation`, linked via relations to the created entity (`created`), one or more agents (`carried_out_by`), and a place (`took_place_at`). This matches Katalon's existing use of Occurrence for events, supports multiple agents/roles, and makes the event independently searchable and describable with its own fields (date, place). Preferred whenever the creation act itself needs more than one fact attached to it.

Plain FRBR (the pre-LRM, non-object-oriented IFLA model) has no event classes at all — only the three direct WEMI relations above are needed. That fits with less structure, but drops the event-level provenance (who, when, where, per creation act) that LRMoo and CIDOC-CRM assume, and would sit awkwardly next to any other event-based CRM/LIDO modeling elsewhere in the data.

## Ontology vs. instance data

This pattern is instance-level record modeling, not ontology construction. LRMoo, CIDOC-CRM, and the RDF FRBRer vocabulary are the actual ontologies — abstract reference models with formally defined classes and properties. Katalon's schema engine (`field_definitions`, vocabularies, `record_subtypes`) is a metamodel in the loose sense (a schema for configuring schemas), but it has no axioms, disjointness constraints, or reasoning; it is a pragmatic cataloguing mechanism, and applying this pattern only produces concrete Work/Expression/Manifestation/event records shaped to be *compatible* with LRMoo/FRBR classes.

Semantic interoperability via RDF / JSON-LD export was implemented in [#351](../../../almanac/architecture/workflows/oai-and-export-mappings.md): `JsonLdFormat` maps `occurrence` records with subtypes `work`/`werk`, `expression`/`ausgabe`, `manifestation`/`ausgabeform` directly to `lrmoo:F1_Work`, `lrmoo:F2_Expression`, and `lrmoo:F3_Manifestation`, and `object` records to `["crm:E22_Human-Made_Object", "lrmoo:F5_Item"]` [6]. Relations with standard codes (`is_realised_in`, `is_embodied_in`, `exemplifies`) or explicit `VocabularyTerm.uri` crosswalks map to `lrmoo:R3_is_realised_in`, `lrmoo:R4_is_embodied_in`, and `lrmoo:R7_exemplifies` [6].

## Status

The serialization crosswalk layer is implemented. Default instance-level `record_subtypes` or database migrations pre-seeding WEMI terms are intentionally not built-in: institutions configure them as needed via schema configuration and relation vocabularies.

# Citations

[1] almanac/concepts/domain/primary-record-types.md
[2] almanac/concepts/metadata/record-subtypes.md
[3] almanac/concepts/relations/generic-relations.md
[4] .agents/knowledge/decisions/vier-bestandstypen.md
[5] almanac/decisions/data/generic-relation-model.md
[6] almanac/architecture/workflows/oai-and-export-mappings.md
