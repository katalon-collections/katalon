---
title: "OAI And Export Mappings"
summary: "Katalon's OAI-PMH endpoint exposes public Elasticsearch records as `oai_dc` XML using configurable metadata mappings with a conservative fallback."
topics: [architecture, workflows, oai-pmh, export, metadata, elasticsearch]
sources:
  - id: oai-api
    type: file
    path: backend/src/katalon/api/v1/oai.py
  - id: oai-sets-api
    type: file
    path: backend/src/katalon/api/v1/oai_sets.py
  - id: oaipmh-service
    type: file
    path: backend/src/katalon/services/oaipmh_service.py
  - id: mapping-service
    type: file
    path: backend/src/katalon/services/metadata_mapping_service.py
  - id: oai-doc
    type: file
    path: docs/05_oai_serialisierungen.md
  - id: mapping-doc
    type: file
    path: docs/10_export_mappings.md
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
  - id: issue-268
    type: web
    url: https://github.com/karkraeg/Katalon/issues/268
---

Katalon's OAI-PMH workflow exposes public indexed records at `/oai` and currently disseminates the `oai_dc` metadata format. The HTTP handler dispatches OAI verbs, queries Elasticsearch with public-record filters, loads optional OAI set definitions, and passes hits to XML serializers [@oai-api]. Export mappings connect `field_definitions` to Dublin Core target paths, so an installation can map schema fields to `dc:title`, `dc:creator`, and other OAI-DC elements without changing the OAI handler [@mapping-service] [@mapping-doc]. The endpoint uses Elasticsearch as its read model, so [Search And Indexing](search-and-indexing) is part of the export path.

## Endpoint And Verb Dispatch

The OAI router is mounted at `/oai`, not under the versioned REST API path, because OAI-PMH is a protocol endpoint rather than a normal `/v1` resource [@oai-doc]. `oai_endpoint()` handles `Identify`, `ListMetadataFormats`, `ListSets`, `ListRecords`, `ListIdentifiers`, `GetRecord`, and bad verbs [@oai-api]. Elasticsearch connection failures return HTTP 503 with `Retry-After: 60` instead of malformed XML from a partial export path [@oai-api].

`Identify` uses the portal site title as repository name when available and falls back to `Katalon`; admin email comes from OAI or default admin settings [@oai-api]. `ListMetadataFormats` currently advertises only `oai_dc`, and the handler rejects other prefixes with `cannotDisseminateFormat` in `ListRecords`, `ListIdentifiers`, and `GetRecord` [@oai-api] [@oaipmh-service].

## Elasticsearch Read Model

`_es_search_for_oai()` always filters list-style OAI queries to `status = public` [@oai-api]. `GetRecord` fetches one Elasticsearch document by ID and returns it only when the stored source has public status [@oai-api]. Date filters become an `updated_at` range, and list responses sort by `updated_at` and `_doc` with page size 100 [@oai-api].

OAI sets are optional filters layered onto that public Elasticsearch query. A set may filter by record type, status, metadata key/value pairs, and a free-text query over title and search text [@oai-api]. The set management API lets users list sets and lets admins or superusers create, update, and delete set definitions [@oai-sets-api].

## Mapping Model

The mapping service defines `oai_dc` as the active format key and allows only the fifteen Dublin Core element paths in `OAI_DC_TARGETS` for that format [@mapping-service]. `get_mapping_index()` joins enabled `MetadataMapping` rows to active `FieldDefinition` rows and returns a nested index by record type and field name [@mapping-service]. `extract_values()` flattens source metadata values from strings, lists, and dictionaries by preferring keys such as `value`, `label`, `term`, `name`, `title`, and `idno` [@mapping-service].

The repository documentation describes the same design intent: `metadata_mappings` is format-neutral, a field can map to multiple target paths, and `oai_dc` is the first productive consumer while later formats such as LIDO or METS/MODS are prepared conceptually [@mapping-doc]. Current code implements the generic mapping read path and OAI-DC validation, but it still advertises and accepts only `oai_dc` at the protocol layer [@oai-api] [@mapping-service].

Container fields are not independently mapped to OAI-DC. The schema editor exposes export mapping controls for top-level fields and explicitly marks `group` fields as not directly exported; sub-field editing has no separate export mapping panel [@schema-screen].

## XML Serialization

`oaipmh_service` builds OAI-PMH XML with `xml.etree.ElementTree`, including response date, protocol namespaces, OAI errors, resumption tokens, record headers, and metadata records [@oaipmh-service]. Resumption tokens encode offset, set, date range, and prefix as base64 JSON, and list responses include a next token when more hits remain [@oaipmh-service].

When a mapping index has entries for a hit's record type, `_hit_to_oai_record()` emits mapped values to the configured Dublin Core target paths [@oaipmh-service]. Without mappings, it falls back to a conservative Dublin Core record: title, first creator-like metadata field, description, keywords as subjects, created date, record type, identifiers, language, and rights where present [@oaipmh-service]. `dc:type` and the OAI identifier are still added when mapped output does not already supply type [@oaipmh-service].

## Consequences For Future Formats

Adding another export format is not only a serializer change. The current docs call out the need to register the format in `ListMetadataFormats`, centralize prefix validation, and choose the serializer from a prefix-to-function registry before formats such as LIDO can be active [@oai-doc]. Until that registry exists, export mappings may be format-neutral in storage, but runtime OAI dissemination is intentionally limited to `oai_dc` [@oai-api] [@mapping-service].

This page is about record export through OAI-PMH. Vocabulary Linked Open Data is a separate track: Katalon has REST JSON for vocabularies, but no SKOS/JSON-LD vocabulary publication surface yet [@issue-268]. The current minimal plan for that track starts with public vocabulary boundaries, dereferenceable term URLs, SKOS output, and persisted authority match URIs before any SPARQL endpoint or broad record-RDF mapping [@issue-268].
