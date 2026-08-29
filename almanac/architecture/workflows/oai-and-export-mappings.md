---
title: "OAI And Export Mappings"
summary: "Katalon disseminates records via OAI-PMH and a direct Export area using a pluggable metadata-format registry; a format is offered only once fields are mapped to it."
topics: [architecture, workflows, oai-pmh, export, metadata, elasticsearch]
sources:
  - id: oai-api
    type: file
    path: backend/src/katalon/api/v1/oai.py
  - id: export-api
    type: file
    path: backend/src/katalon/api/v1/export.py
  - id: oai-sets-api
    type: file
    path: backend/src/katalon/api/v1/oai_sets.py
  - id: oaipmh-service
    type: file
    path: backend/src/katalon/services/oaipmh_service.py
  - id: export-service
    type: file
    path: backend/src/katalon/services/export_service.py
  - id: format-service
    type: file
    path: backend/src/katalon/services/metadata_format_service.py
  - id: format-abc
    type: file
    path: backend/src/katalon/integrations/metadata_format.py
  - id: mapping-service
    type: file
    path: backend/src/katalon/services/metadata_mapping_service.py
  - id: oai-doc
    type: file
    path: docs/05_oai_serialisierungen.md
  - id: mapping-doc
    type: file
    path: docs/10_export_mappings.md
  - id: export-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenExport.tsx
  - id: issue-268
    type: web
    url: https://github.com/karkraeg/Katalon/issues/268
---

Katalon exposes records two ways: the OAI-PMH protocol endpoint at `/oai` for harvesters, and a direct Export area in the admin UI for CSV/JSON dumps and one-off XML downloads [@oai-api] [@export-api]. Both read paths share the same building blocks: a field-to-target-path mapping (`metadata_mappings`) and a pluggable metadata-format registry (`metadata_formats`) that decides which XML shape a mapped field lands in [@mapping-service] [@format-service]. Fields marked internal (`is_public = false`) are excluded from the index and cannot be mapped.

## Format Registry (Plugin Pattern)

`metadata_format_service` mirrors `authority_service`'s adapter pattern: a `_BUILTIN` dict holds always-available `MetadataFormat` instances (`OaiDcFormat`, `LidoFormat`, `MetsModsFormat`), and rows in `metadata_formats` either patch config onto a builtin instance (same `id`) or dynamically import a custom `adapter_class` (new `id`) [@format-service] [@format-abc]. There is no `is_enabled` toggle — presence of a row is the override signal, and per-format visibility is driven by whether any field is actually mapped to it, not by an admin switch. The registry cache is process-lifetime; there is currently no endpoint that calls `invalidate_cache()` after a `metadata_formats` write (unlike `authority.py`'s `PATCH` handler for authority sources), so adding or overriding a format needs an `api` container restart to take effect.

Each `MetadataFormat` declares `targets` (the valid `target_path` values for mapping validation and the admin mapping-table dropdown), `schema_url`/`namespace` (for OAI's `ListMetadataFormats`), and a `render(hit, mappings)` method that builds one XML element from an Elasticsearch hit plus that record type's mappings [@format-abc]. `metadata_mapping_service.validate_mapping_target()` looks up `targets` from the registry instead of a hardcoded set, so validation is format-agnostic [@mapping-service].

## OAI-PMH: Endpoint And Format Gating

`oai_endpoint()` handles `Identify`, `ListMetadataFormats`, `ListSets`, `ListRecords`, `ListIdentifiers`, `GetRecord`, and bad verbs [@oai-api]. `_available_formats()` intersects the registry's formats with `mapped_format_keys()` (format keys that have at least one enabled, non-deleted, public field mapping) — that intersection is what `ListMetadataFormats` advertises and what every other verb validates `metadataPrefix` against [@oai-api] [@mapping-service]. There is no default-to-`oai_dc` fallback for unmapped record types anymore: `_es_search_for_oai()` additionally restricts `ListRecords`/`ListIdentifiers` to `mapped_record_types(prefix)`, and `GetRecord` rejects a hit whose `record_type` isn't in that set with `idDoesNotExist` [@oai-api].

Elasticsearch connection failures still return HTTP 503 with `Retry-After: 60` [@oai-api]. OAI sets remain optional filters layered onto the public-only Elasticsearch query (record type, status, metadata key/value, free-text) [@oai-sets-api].

## Rendering

`oaipmh_service._hit_to_oai_record()` builds the OAI envelope (header, identifier, datestamp, setSpec) and delegates the `<metadata>` payload to `metadata_format.render(hit, mappings)` — the OAI service itself has no format-specific XML logic anymore [@oaipmh-service]. `OaiDcFormat.render()` emits only mapped Dublin Core elements plus two always-structural ones (`dc:type` from `record_type`, `dc:identifier` as the OAI id) — the old heuristic fallback that guessed title/creator/description/subject/language/rights from generic field names when no mapping existed has been removed; unmapped record types simply aren't offered the format at all [@oaipmh-service].

`LidoFormat` and `MetsModsFormat` cover a pragmatic subset of their respective schemas (title, type, description/abstract, one event date, one actor, rights for LIDO; title, name, type, origin date, abstract, access condition, identifier, language for MODS) and share a generic `append_path()` helper that turns a `/`-separated `target_path` into a nested element chain — reusable for any hierarchical XML format, not just these two [@format-abc].

## Export Area (Admin UI)

`export.py` serves `/v1/export/formats` (CSV/JSON always; XML formats only if `mapped_record_types()` includes the requested type) and `/v1/export/{record_type}` (streamed download) [@export-api]. CSV/JSON dumps read directly from the Postgres tables (not Elasticsearch) via `export_service.stream_csv/json`, so they reflect canonical data including internal fields, independent of reindex staleness [@export-service]. XML dumps reuse the same Elasticsearch scroll + format-registry rendering path as OAI, via `integrations.elasticsearch.iter_hits_by_type()` (no public-status restriction, since this is an authenticated admin action) [@export-service].

The Format-Mapping table that used to live per-field inside the Schema editor (`ScreenSchema.tsx`'s `ExportMappingPanel`) has moved to its own tab in `ScreenExport.tsx`: one table, fields × registered formats, driven by `GET /v1/metadata-mappings/formats` [@export-screen] [@mapping-doc].

## Adding A New Format

No changes to `oai.py`, `oaipmh_service.py`, or `export.py` are needed: write a `MetadataFormat` subclass and add one `metadata_formats` row (new `adapter_class` for a new format, or a config patch on an existing `id` to extend/override targets). Step-by-step with a worked MARC21XML example is in [@oai-doc]. This closes out the "Consequences For Future Formats" gap noted in the prior version of this page — LIDO and METS/MODS are now productive built-ins rather than conceptual placeholders.

This page is about record export through OAI-PMH and the Export area. Vocabulary Linked Open Data is a separate track: Katalon has REST JSON for vocabularies, but no SKOS/JSON-LD vocabulary publication surface yet [@issue-268].
