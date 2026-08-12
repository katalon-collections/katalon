---
title: "Inherited Fields In Elasticsearch"
summary: "Katalon denormalizes selected fields from linked records into Elasticsearch documents instead of copying them back into source records."
topics: [decisions, search, indexing, relations]
sources:
  - id: decision-note
    type: file
    path: .agents/knowledge/decisions/inherited-fields-es.md
  - id: search-service
    type: file
    path: backend/src/katalon/services/search_service.py
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
---

Katalon treats inherited relation fields as Elasticsearch denormalization, not as persisted copies inside PostgreSQL records. Relation field settings name target fields to inherit, and the search document builder embeds selected metadata under `linked_<type>s` arrays and keyword-safe inherited facet fields [@schema-screen] [@search-service]. The source records and generic relation rows stay authoritative, while [Search And Indexing](../../architecture/workflows/search-and-indexing) explains the search-side projection boundary [@decision-note].

## Context

The motivating case was a linked-record search need: an Object linked to an Occurrence with a publication year should be findable by that year, even though the year belongs to the Occurrence and not to the Object [@decision-note]. Persisting inherited values back into the Object would make the Object metadata carry data owned by another record. That would blur the boundary maintained by [Generic Relations](../../concepts/relations/generic-relations), where links connect records without making either endpoint own the other's fields.

Inherited fields are configured in the Admin schema editor. For a relation field, `ScreenSchema` shows checkboxes for fields on the target type and writes the selected names into `settings.inherited_fields` together with `settings.target_type` [@schema-screen]. The indexer reads that same key; the Portal facet configuration offers these fields as inherited facets [@schema-screen] [@search-service].

## Decision

The search index is the only denormalized storage for inherited fields. During `build_index_doc()`, Katalon reads top-level field definitions for the record type, finds relation fields, and collects `settings.inherited_fields` for the configured `settings.target_type` [@search-service]. `_load_linked_data()` then reads outgoing relations for the current record, loads the target records, extracts only the configured metadata keys, and returns entries shaped as `{"linked_<type>s": [{"id", "relation_type", "inherited"}]}` plus `facet_inherited_<type>_<field>` keyword values [@search-service].

The decision note also fixes the cascade boundary at one relation hop. When a linked record changes, records that point to it may be reindexed, but inherited values are not recursively propagated through arbitrary chains [@decision-note]. That keeps the index repair problem bounded in a graph where relations can connect many record types.

## Consequences

Search can answer linked-field questions without changing the relational data model. PostgreSQL still stores source metadata on the record that owns it, and relations still describe edges between records; Elasticsearch receives a query-optimized projection of selected linked fields [@decision-note] [@search-service].

The cost is index maintenance. A changed linked record must cause dependent documents to be rebuilt for the inherited values to stay current, and one-hop propagation means deeply chained inheritance is intentionally out of scope [@decision-note]. Maintainers should treat inherited fields as search material and avoid using `linked_<type>s` data as a source of truth for editing workflows.
