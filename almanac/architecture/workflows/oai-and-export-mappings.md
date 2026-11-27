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
  - id: export-profiles-api
    type: file
    path: backend/src/katalon/api/v1/export_profiles.py
  - id: export-mapping-sets-api
    type: file
    path: backend/src/katalon/api/v1/export_mapping_sets.py
  - id: app
    type: file
    path: backend/src/katalon/main.py
  - id: rdf-service
    type: file
    path: backend/src/katalon/services/rdf_service.py
  - id: jsonld-format
    type: file
    path: backend/src/katalon/integrations/jsonld_format.py
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
  - id: export-context-service
    type: file
    path: backend/src/katalon/services/export_context_service.py
  - id: oai-doc
    type: file
    path: docs/03_oai_serialisierungen.md
  - id: mapping-doc
    type: file
    path: docs/07_export_mappings.md
  - id: export-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenExport.tsx
  - id: issue-268
    type: web
    url: https://github.com/karkraeg/Katalon/issues/268
  - id: echoes-d62
    type: file
    path: almanac/reference/echoes-d62-interoperability.md
  - id: lido-builder
    type: file
    path: backend/src/katalon/integrations/lido/builder.py
  - id: authority-uris
    type: file
    path: backend/src/katalon/integrations/authority_uris.py
  - id: licenses
    type: file
    path: backend/src/katalon/integrations/licenses.py
  - id: export-report
    type: file
    path: backend/src/katalon/services/export_report_service.py
  - id: oai-state
    type: file
    path: backend/src/katalon/services/oai_state_service.py
  - id: media-service
    type: file
    path: backend/src/katalon/services/media_service.py
  - id: place-service
    type: file
    path: backend/src/katalon/services/place_service.py
---

Katalon exposes records two ways: the OAI-PMH protocol endpoint at `/oai` for harvesters, and a direct Export area in the admin UI for CSV/JSON dumps and one-off XML downloads [@oai-api] [@export-api]. `main.py` mounts OAI without `/v1` and mounts export under the authenticated `/v1` API surface [@app]. Both read paths share the same building blocks: versioned mapping sets (`export_mapping_sets` and `export_mapping_rules`) and a pluggable metadata-format registry (`metadata_formats`) that decides which XML shape a mapped field lands in [@mapping-service] [@format-service] [@export-mapping-sets-api]. Fields marked internal (`is_public = false`) are excluded from the index and cannot be mapped.

**No format ships pre-mapped.** Katalon's internal storage is a freely configurable field schema (`field_definitions`), not a fixed data model tied to any one export standard — closer to how Pandoc reads/writes many document formats through one internal representation than to a system that assumes a schema and gives you instant "data sites." An instance curator must deliberately map that internal schema onto each output format's target fields through the Export area before that format even appears as offered (`mapped_format_keys()` / `mapped_record_types()` below) — there is no built-in assumption about which vocabulary a given field's values should round-trip into. This is by design: the same institution can serialize one object record as LIDO for a museum aggregator and as METS/MODS for a library aggregator, with two independently curated mappings, and can add further formats (`metadata_formats` row + a `MetadataFormat` subclass, see "Export Area" below) without touching the schema. A field-based *importer* that reads existing LIDO/MODS/Dublin-Core records back into this internal schema is planned but not yet built.

## Format Registry (Plugin Pattern)

`metadata_format_service` mirrors `authority_service`'s adapter pattern: a `_BUILTIN` dict holds always-available `MetadataFormat` instances (`OaiDcFormat`, `LidoFormat`, `MetsModsFormat`, `JsonLdFormat`), and rows in `metadata_formats` either patch config onto a builtin instance (same `id`) or dynamically import a custom `adapter_class` (new `id`) [@format-service] [@format-abc]. There is no `is_enabled` toggle — presence of a row is the override signal, and per-format visibility is driven by whether any field is actually mapped to it, not by an admin switch. The registry cache is process-lifetime; there is currently no endpoint that calls `invalidate_cache()` after a `metadata_formats` write (authority sources instead reload their registry on every lookup), so adding or overriding a format via DB requires an app restart [@format-service].
Each `MetadataFormat` declares `targets` (valid `target_path` values), `schema_url`/`namespace`, a `capabilities()` profile (groups, localized labels/help, accepted source kinds, validator dependencies), `validate_mapping(mapping_set)` for format-level diagnostic checks, and a `render(hit, mappings)` method that builds XML elements from an Elasticsearch hit plus that record type's `CompiledMappingSet` [@format-abc]. `metadata_mapping_service.validate_mapping_target()` and the format validator ensure mapping targets remain sound [@mapping-service]. The API exposes capability profiles via `/v1/export-profiles` and enriches `/v1/metadata-mappings/formats` [@export-profiles-api].

`oai_endpoint()` handles `Identify`, `ListMetadataFormats`, `ListSets`, `ListRecords`, `ListIdentifiers`, `GetRecord`, and bad verbs [@oai-api]. `_available_formats()` intersects the registry's formats with `mapped_format_keys()` (format keys that have at least one enabled, non-deleted, public field mapping) — that intersection is what `ListMetadataFormats` advertises and what every other verb validates `metadataPrefix` against [@oai-api] [@mapping-service]. There is no default-to-`oai_dc` fallback for unmapped record types anymore: `_es_search_for_oai()` additionally restricts `ListRecords`/`ListIdentifiers` to `mapped_record_types(prefix)`, and `GetRecord` rejects a hit whose `record_type` isn't in that set with `idDoesNotExist` [@oai-api]. OAI-PMH 2.0 (section 3.4) requires every repository to offer `oai_dc`, so an instance that harvesters should treat as compliant needs a published `oai_dc` mapping set; Katalon deliberately ships no built-in fallback mapping, because the useful Dublin Core fields differ per schema (a YAML mapping set is the portable way to add one).

`baseURL` comes from `OAI_BASE_URL` or, when empty, from the request (proxy headers); `adminEmail` from `Settings.oai_contact_email` [@oai-api]. Elasticsearch connection failures still return HTTP 503 with `Retry-After: 60` [@oai-api]. OAI sets remain optional filters layered onto the public-only Elasticsearch query (record type, status, metadata key/value, free-text) [@oai-sets-api]. `ListRecords`/`ListIdentifiers` resumption tokens carry an Elasticsearch `search_after` cursor (the previous page's last hit sort values), not a numeric offset — `_es_search_for_oai()` always sorts by `updated_at` then `_doc` for a stable tiebreak, so harvesting a repository has no depth ceiling regardless of its size, unlike offset-based `from`/`size` paging [@oai-api] [@oaipmh-service]. The token still carries a running `cursor` count purely for the `resumptionToken` XML attribute; it does not drive the query.

## Rendering

`oaipmh_service._hit_to_oai_record()` builds the OAI envelope (header, identifier, datestamp, setSpec) and delegates the `<metadata>` payload to `metadata_format.render(hit, mappings)` — the OAI service itself has no format-specific XML logic anymore [@oaipmh-service]. Mappings reach the renderer as a structured `CompiledMappingSet` (preserving rule keys, `source_kind`, `settings`, and `sort_order`), while transparently supporting legacy dictionary access for backward compatibility [@format-abc]. Published mappings are compiled per record type. Format adapters evaluate rule `settings` (such as prefixes) and process rules in configured order.

Relation-sourced mapping rules (`source_kind=relation`) resolve against `ExportRecordContext.relations`, which `export_context_service.build_export_context_from_db()` populates from both directions of the generic `relations` table: outbound (`from_type`/`from_id` match the exported record) and inbound (`to_type`/`to_id` match it), each tagged with `direction: "outbound" | "inbound"` [@export-context-service]. A rule's `source_config.direction` (default `outbound`) selects which side to read; `relation_type` and `target_field` narrow further and pull a specific public field off the linked record. `_EXCLUDED_RELATION_TARGET_TYPES` (`storage_location`, `procedure`) is enforced symmetrically in both directions, so internal logistics/process records never surface in a public export regardless of which side of the relation points at them. Linked records that are soft-deleted (`deleted_at` set) or whose status is not in `PUBLIC_STATUSES` are dropped, and a soft-deleted record itself cannot be exported (the builder raises, the export endpoint answers 404). Targets are loaded with one query per linked type and public field definitions once per type.

The copy of the context stored in the search index (`build_index_doc`) is capped: if a record has more than `INDEX_MAX_INBOUND_RELATIONS` (200) inbound relations, they are left out and counted in `inbound_relations_omitted`. A large collection otherwise carried every member record with all its public values (up to 46 MB per document on the BPK data), which made bulk requests and reindexing slow. Batch export (`stream_xml`) and OAI-PMH (`ListRecords`, `GetRecord`) call `refresh_index_contexts()`, which rebuilds the full context from PostgreSQL for exactly those hits, so exports stay complete [@export-context-service].

The index copy is also rebuilt when it is stale: `ExportRecordContext.schema_version` is stored with every context and mirrored as the top-level, queryable `export_context_version`. `index_context_is_stale()` treats copies below `EXPORT_CONTEXT_VERSION` (`integrations/metadata_format.py`) as stale, including copies written before the version existed. Without this, an update that changes the context shape (1.42 → 1.43 added `iiif_base`, `credit_line`, event places and `pref` URIs) served incomplete but XSD-valid LIDO over OAI until someone ran a full reindex, while the preview (built from the database) looked correct. Bump `EXPORT_CONTEXT_VERSION` whenever exporters read new or reshaped context data. `GET /v1/admin/index-health` reports the number of stale copies (`stale_export_contexts`), and `scripts/gen_release_metadata.py` sets `reindex_required` in `katalon-release.json` when the constant differs from the previous tag, which `katalon-cli update` turns into a reindex prompt (`--reindex` runs it).

`filter_public_metadata()` keeps the schema order of fields and group sub-fields (`load_public_fields` orders by `sort_order`, then name). It used a `set` for group children before, whose iteration order depends on the per-process hash seed: the API (preview) and the worker (index, OAI) produced different key orders for the same group, and every exporter that takes the first value of a group (`_item_from_value` for a group mapped as a whole) emitted different data depending on the process.

`OaiDcFormat.render()` emits only mapped Dublin Core elements plus two always-structural ones (`dc:type` from `record_type`, `dc:identifier` as the OAI id) — the old heuristic fallback that guessed title/creator/description/subject/language/rights from generic field names when no mapping existed has been removed; unmapped record types simply aren't offered the format at all [@oaipmh-service].

`LidoFormat` and `MetsModsFormat` cover their respective domain schemas. `MetsModsFormat` follows the DFG-Viewer METS profile (the structure Kitodo/Goobi produce and library aggregators expect), without knowing any particular aggregator: descriptive MODS 3.8 in `<mets:dmdSec>`; in `<mets:amdSec>` the rights sections `RIGHTS_MODS` and `RIGHTS_DVRIGHTS` (`dv:rights`) plus, when the record has a `canonical_url`, a `digiprovMD` with `dv:links` (`dv:reference`/`dv:presentation`); public media only in `<mets:fileSec>` (IIIF images as a full JPEG in `DEFAULT` and a 400px JPEG in `THUMBS`, other media by URL); a logical `structMap` with one div whose `TYPE` is `institution_config.mets_logical_type` (a DFG structure-set value such as `monograph` or `illustration`; default: the record type); a physical `structMap` (`physSequence` with one `page` div per image) and `structLink` from the logical div to the physical ones. MODS rendering details: `mods:name` gets `displayForm` (and the legacy `namePart`), `@type` from the shared `actor_types` config (subtype → person/corporation/family), `@valueURI` from the first `actor_id_fields` identifier of the related record, and with `settings.role_code` a MARC relator `roleTerm[@type='code']`; `mods:originInfo/mods:dateCreated` turns the first EDTF-lite value into ISO 8601 dates (`point` start/end for ranges, `qualifier` approximate/questionable) plus a `displayDate`, while free text only becomes `displayDate`; `originInfo`, `physicalDescription` and `recordInfo` collect values of all rules in one element; `recordIdentifier` takes `settings.source`, `relatedItem` takes `settings.type`; identical `accessCondition` values appear once, and `settings.limit` caps the values of any rule (e.g. one licence per record). The targets are the 20 top-level elements of the Library of Congress MODS specification plus `originInfo/publisher`, `originInfo/place/placeTerm`, `subject/geographic` and `physicalDescription/form` (8 core targets displayed by default, the rest addable via the MODS element dropdown; repeatable elements like `mods:note` can be added multiple times as discrete navigator entries with custom note types). Aggregator rules (e.g. which structure types, which authority URIs or how many licences are accepted) belong in the instance's mapping set, not in the builder. For LIDO, events are structured as coherent entities (`lido_events` config in `institution_config`, each entry `{id, type, type_concept_uri}`; production, creation, use, acquisition or custom events). Each event bundles eventType (with `conceptID` from `type_concept_uri`, source "LIDO-Terminologie"), actors in role, date, places, materials/techniques and event descriptions into its own `<lido:eventSet>`; per-event targets are `lido:events/{id}/{type|actor|date|earliest_date|place|materials_tech|materials_tech_term|description}`. `lido:objectWorkType` accepts several rules side by side: a mapped authority/vocabulary field (optionally with `settings.type`), free text, or the record subtype's normdaten from `record_subtypes` (preferred concept plus `concept_alternatives`, emitted as `lido00169`/`lido00170`). Selecting subtype authority data requires every configured object subtype to have authority data before the mapping can be published. New LIDO object drafts map `label` to the title target and copy the portal institution name when present. A LIDO mapping set requires title and object work type mappings.

### LIDO Builder Rules And Rights Checks

`lido/builder.py` renders in XSD order and applies the same output rules to every element [@lido-builder]: terminology attributes use URIs from one `LIDO_TERMS` table (preferred/alternative, `repositorySet` current, `conceptID` type `lido00099`, local IDs `lido00100`); text is entity-decoded, stripped of real HTML tags (`metadata_format.HTML_TAG_RE`; a `<` followed by a space, as in vocabulary qualifiers like „Himmel < religiös >“, stays text and is escaped by the serializer) and trimmed (incl. NBSP/newlines); empty values create no element or attribute, and empty wraps are pruned afterwards; identical repeated siblings are deduplicated (e.g. one place reached through two publishers). Field rules address group sub-fields as `group.child`. Authority values and pasted authority URLs become canonical URIs through `integrations/authority_uris.py` (GND, Wikidata, AAT, TGN, ULAN, VIAF, Iconclass notations only, GeoNames always as `https://sws.geonames.org/{id}/`) [@authority-uris]; license URIs keep their stored spelling and get display labels through `integrations/licenses.py`; only an `allowed_license_uris` list rewrites them into the list's spelling (Katalon prefers no http/https form) [@licenses].

Per-rule `settings` carry the structure: `type` (objectWorkType, classification, objectDescriptionSet — the old `/short` and `/condition` targets stay as aliases), `description` (inscriptions), `measurement_type`/`unit` (structured `measurementsSet`; "9,2 cm" → value `9.2`, unit `cm`, plus a composed `displayObjectMeasurements`), `role`/`role_uri` (actors), `label_field` (date), `kind` (`material`/`technique`), `include_ancestors`/`path_separator` (place: off by default; when enabled, `namePlaceSet/appellationValue` joins public ancestor titles from root to place with `path_separator`, default `" > "`, without emitting `partOfPlace`), `lang`. Relation rules may follow a second step via `source_config.via` (object —creator→ entity —ansaessig→ place). `ExportRelation.target_relations` holds these second-level relations; `collect_via_relation_types()` loads only the via types used by published mapping sets (preview adds the draft's), so the index copy does not grow by every relation of every related record. Place relations (first- and second-level) also carry `target_ancestors` populated via `place_service.load_place_chains(public_only=True)` (one query per hierarchy level) and `ancestors_of()` (the same portal visibility rule, stopping at non-public parents); this bumped `EXPORT_CONTEXT_VERSION` to 4 [@export-context-service] [@place-service]. Actor and place IDs come from public authority/URL fields of the related record listed in `institution_config.actor_id_fields` / `place_id_fields` (or per rule). An entry may address a group sub-field (`normdaten.ag_gnd`); a group named as a whole contributes all its sub-values, each with the source recognised from its URI (GND, VIAF, Wikidata, …), and the entry's `source` applies only where the URI gives none; `actor_types` maps entity subtypes to person/corporation. URL field dicts `{value, label}` with any `http(s)` URL emit `value` as `conceptID` (or license URI in `resource_rights_fallback: object_field:`) and `label` as `term` (falling back to the URL when `label` is empty) via `_item_from_value()`. Second-level data in the index copy is refreshed only when the exported record itself is reindexed (same limitation as first-level `target_values`). For direct place relations, `target_ancestors` is refreshed across the subtree: each place index document carries a non-indexed `place_path_key` (parent, status, title), and when `index_record_task` finds it missing or changed (including direct children reindexed by `delete_place` with `reparent=true`), `cascade_reindex_task` rebuilds the records linked to that place and all of its descendants once each. Second-level `target_ancestors` on `via` paths still keep the old path in the index copy until the exported record is reindexed (`katalon-manage reindex --type object`).

`richtext` values (Markdown, top-level and group sub-fields) become plain text in the export context (`integrations/markdown_text.py`: emphasis/heading/link syntax and backslash escapes removed, hard breaks become newlines), so no format emits Markdown syntax; the change bumped `EXPORT_CONTEXT_VERSION` to 3 [@export-context-service].

`date` values (EDTF-lite) yield `displayDate` in the portal's wording ("nach 1905") plus `earliestDate`/`latestDate` with the original precision, computed at render time from the stored value. The export context carries `uri`/`exact_match_uris` on vocab values (one query for all terms), `width`/`height`/`credit_line`/`rights_statement_label` and the IIIF base (encoded storage key, as Cantaloupe expects) on media, and the record's own `created_at`/`updated_at`, which `recordMetadataDate` uses (`lido00471`, else `lido00470`) instead of the export time, formatted like the OAI datestamp (`metadata_format.utc_timestamp()`: `YYYY-MM-DDThh:mm:ssZ`, UTC).

Structural record metadata needs no rules: `lidoRecID` (`lido00100`, formatted as `{isil}{sep}{idno}` when ISIL is configured, using `institution_config.lido_rec_id_separator`, default `"--"`, shared with `export_report_service`), `recordID` (`lido00100`), `recordType` (`lido00141`), `recordSource` and `repositoryName` as ISIL legal bodies (`https://sigel.staatsbibliothek-berlin.de/suche?isil=…`), `recordRights` (CC0 by default, `record_rights`; then `rightsHolder` if `record_rights_holder`, then the `lido:recordWrap/lido:recordRights/lido:creditLine` target). `rights_work_holder` adds the institution as `rightsWorkSet/rightsHolder`; `location_place_ids` and `work_ids` extend the repository. With `resource_sets: true` every public medium becomes a `resourceSet`, primary first: `resourceID`, master (`lido00464`, IIIF `full/max` or download URL with the real MIME type) and preview (`lido00465`, IIIF `!400,400`) representations, optional IIIF manifest link (`resource_iiif_manifest`), `resourceType` `image` for images, and `rightsResource` (license URI + label, medium rights holder or institution, credit line). Media without a license use `resource_rights_fallback` (`none`, `object_field:<group.child>`, or `default` = `resource_rights_default_uri`). Single uploads, metadata/rights/visibility/primary edits, deletion, and images becoming IIIF-ready move the object's `updated_at` via `media_service.touch_object()` and trigger reindexing, so `recordMetadataDate`, the OAI datestamp and `from=` harvests pick it up [@media-service]. Image uploads are reindexed when the worker marks the image ready; non-image uploads are reindexed immediately through the API (see [Media And IIIF](media-and-iiif)).

Rights checks are switched on per mapping set, never per recipient: `require_media_license` (every public medium needs a license, fallback included) and `allowed_license_uris` (list; empty = no check; applies to media and `recordRights`, literal comparison after spelling normalization). A recipient's requirements (e.g. the DDB license basket) live only in its mapping configuration, see the example `backend/tests/fixtures/lido_ddb_mapping.yaml` and the rule "Export: aggregator-agnostisch" in `AGENTS.md`. `katalon-manage lido-report --mapping-set <id> [--output file.csv]` (`export_report_service`) checks all public records of the set's type from PostgreSQL, prints counts per problem and writes one CSV row per problem [@export-report]. Only LIDO 1.0 is rendered; `institution_config.lido_version` is validated so 1.1 structures can be added later.

`JsonLdFormat` provides Linked Data export following CIDOC-CRM and LRMoo standards: it maps primary types (`occurrence` to `lrmoo:F1_Work`, `lrmoo:F2_Expression`, `lrmoo:F3_Manifestation`, `crm:E5_Event`; `object` to `lrmoo:F5_Item` / `crm:E22_Human-Made_Object`; `entity` to `crm:E21_Person` / `crm:E74_Group`; `place` to `crm:E53_Place`; `procedure` to `crm:E7_Activity`; `collection` to `crm:E78_Curated_Holding`; `storage_location` to `crm:E53_Place`), resolves relations into standard properties (`lrmoo:R3_is_realised_in`, `lrmoo:R4_is_embodied_in`, `lrmoo:R7_exemplifies`, `crm:P14_carried_out_by`), embeds canonical vocabulary term URIs as `skos:Concept`, and serializes as XML `<json_ld>` in OAI-PMH (`metadataPrefix=json_ld`). Canonical entity URIs point to the canonical base URL.

### RDF Contract And Semantic Guarantees

As explored in Issue #359, Katalon enforces clear semantic boundaries between core guarantees and local instance configuration:

1. **Core Graph Skeleton (Katalon Responsibility):** JSON-LD export assigns stable CIDOC-CRM/LRMoo classes to Katalon's record families, resolves generic relations into known semantic properties where possible, and emits vocabulary terms as `skos:Concept` nodes with canonical URIs when the vocabulary data provides them [@jsonld-format] [@rdf-service].
2. **Instance Custom Mappings (User Responsibility):** Arbitrary metadata fields from `field_definitions` are mapped via versioned `export_mapping_sets` rules by instance curators. Katalon guarantees the graph skeleton, while individual communities (e.g. EFGAMP gaming ontologies, archival collections) define and map their custom semantic properties through the admin interface without breaking the core graph skeleton.
3. **No Synchronous Live-SHACL Overhead:** Runtime validation (e.g. via `pyshacl`) is deliberately omitted from the export request path to prevent high-latency blocking; contract verification stays strictly within CI and offline test suites.

### Per-Record Required-Field Guards

`validate_mapping()` only checks the mapping *configuration* once (e.g. "is a title target mapped at all"); it says nothing about whether a given record's data actually resolves to a value through that mapping. `MetadataFormat.required_field_errors(ctx, mapping_set)` closes that gap: a per-record, per-value check that returns German error strings when a format's genuinely schema-required fields resolve empty, so callers can refuse to emit broken XML instead of shipping e.g. an empty `<lido:appellationValue/>` [@format-abc]. The default implementation returns nothing (opt-in per format).

Only `LidoFormat` currently overrides it, via `lido.builder.missing_required_fields()`, checking that the title and `objectWorkType` targets both resolve to a non-empty value for the record at hand, plus the configured rights checks (`rights_check_errors()`) [@lido-builder]. `MetsModsFormat` needs no override — its title always falls back to `record.title or idno`, so it can't resolve empty. `OaiDcFormat` deliberately has none either: `oai_dc.xsd` makes every Dublin Core element optional (`minOccurs="0"`), and an existing test (`test_get_record_requires_mapping_no_title_without_it`) documents that an unmapped `dc:title` is supported, not broken, output.

Three call sites act on `required_field_errors()`:
- `GET /v1/export/{record_type}/{record_id}` (single-record) raises `422` with the missing-field reasons [@export-api].
- `export_service.stream_xml()` (batch download) skips the record, logs a warning, and — if anything was skipped — appends one trailing `<!-- N Datensätze übersprungen (Pflichtfelder fehlen): ... -->` comment before the closing envelope tag, so the rest of the file stays valid [@export-service].
- `oaipmh_service.get_record()`, `list_records()` and `list_identifiers()` emit a `<header status="deleted">` (datestamp = the record's `updated_at`) instead of metadata, so incremental harvesters drop an earlier copy [@oaipmh-service].
- The mapping preview lists the record's errors as `record_invalid` warnings.

### Deleted Records

Identify declares `deletedRecord=transient`. `oai_record_states` (`record_type`, `record_id`, `deleted_at`) holds one row per record that has been public: `search_service.index_record()` calls `oai_state_service.track()` in the same transaction as the record change (public → row with `deleted_at = NULL`, otherwise `deleted_at = now` on an existing row), `remove_record()` marks it withdrawn [@oai-state]. Records that were never public get no row, so their identifiers never leave the system. Migration 0083 seeds all currently public records; withdrawals before that are unknown (hence "transient"). Bulk reindexing does not touch the table.

`ListRecords`/`ListIdentifiers` page through live records (Elasticsearch, `search_after`) first, then through deleted rows ordered by `(deleted_at, record_id)`; the resumption token carries `ph` (phase) and `t` (complete list size) [@oai-api]. `from`/`until` filter `deleted_at`. Sets with metadata, status or free-text filters report no deletions, record-type sets only theirs. `GetRecord` answers a deleted header when the identifier has a withdrawn row and no public hit.

## Export Area (Admin UI)

`export.py` serves `/v1/export/formats` (CSV/JSON always; XML formats only if `mapped_record_types()` includes the requested type), `/v1/export/{record_type}` (streamed batch download), and `/v1/export/{record_type}/{record_id}` (single-record export) [@export-api]. CSV/JSON dumps read directly from the Postgres tables (not Elasticsearch) via `export_service.stream_csv/json`, so they reflect canonical data including internal fields, independent of reindex staleness [@export-service]. XML batch dumps stream valid schema-conformant root envelopes defined per format adapter via `MetadataFormat.render_batch_envelope()` and `render_batch_item()` (e.g., `<lido:lidoWrap>` for LIDO, `<mets:metsCollection>` for METS/MODS) [@format-abc] [@export-service].
Rule settings are rendered generically from each target's `settings_schema` (`SourcePicker.tsx`: text, `type: "boolean"` → checkbox with optional `visible_when` for dependent settings, `enum` → select, `widget: "field"` → field picker; `supports_via` adds the second-relation inputs); LIDO event sub-targets take theirs from `ExportProfileCapabilities.template_settings`. Field pickers offer group sub-fields as `group.child`. The LIDO institution editor has a section "Prüfregeln und Lieferangaben" (`LidoDeliverySettings.tsx`) for `lido_rec_id_separator`, the rights checks, resource, rights-holder and authority-field keys; other non-string `institution_config` values are edited as JSON in the free key/value rows instead of being stringified. The Format-Mapping workspace in `ScreenExport.tsx` (`MappingWorkspace.tsx`) enables live mapping configuration with format-specific capability trees (including LIDO materials/technique `eventMaterialsTech/displayMaterialsTech`), real-time diagnostics, an interactive XML preview with "Copy XML" and "Download XML" actions (the preview API takes a record UUID or inventory number, `MappingPreviewRequest.record_id`), as well as portable YAML export and import (`GET /v1/export-mapping-sets/{set_id}/yaml` and `POST /v1/export-mapping-sets/import-yaml`) for sharing, version control, and cross-instance bootstrapping [@export-screen] [@mapping-doc] [@export-mapping-sets-api].

Single-record export is available at `GET /v1/export/{record_type}/{record_id}?format=...`:
- For RDF serializations (`jsonld`, `turtle`), requests delegate to `rdf_service.handle_single_record_export()` with content negotiation [@rdf-service].
- RDF is the public view unless the caller has read permission for the record type: metadata goes through the public projection (relation field targets checked), and only relations to public, non-deleted portal records (object, entity, place, occurrence, collection) are serialized. `export_single_record`/`serialize_record_to_jsonld` default to `public=True`, which also covers the Oxigraph sync [@rdf-service].
- For XML formats (`lido`, `mets_mods`, etc.), requests load canonical records directly via `export_context_service.build_export_context_from_db()`, apply published mapping sets, and render standalone XML documents (`<?xml version="1.0" encoding="UTF-8"?>`) with content-disposition filenames (`{idno or id}.{format}.xml`) [@export-api].
- In the Admin record view (`ScreenForm.tsx`), a generic export dropdown dynamically queries available mapped formats for the record type (`exportApi.listFormats(recordType)`) and triggers direct single-record downloads [@export-screen].
No changes to `oai.py`, `oaipmh_service.py`, or `export.py` are needed: write a `MetadataFormat` subclass and add one `metadata_formats` row (new `adapter_class` for a new format, or a config patch on an existing `id` to extend/override targets). Step-by-step with a worked MARC21XML example is in [@oai-doc]. This closes out the "Consequences For Future Formats" gap noted in the prior version of this page — LIDO and METS/MODS are now productive built-ins rather than conceptual placeholders.

This page is about record export through OAI-PMH and the Export area. Vocabulary Linked Open Data is a separate track: Katalon has REST JSON for vocabularies, but no SKOS/JSON-LD vocabulary publication surface yet [@issue-268]. For how this export surface measures against an external CH-Cloud interoperability standard (ECHOES D6.2), including the concrete SPARQL/SHACL gaps that build on `rdf_service.py`, see [ECHOES D6.2 Interoperability Assessment](../../reference/echoes-d62-interoperability) [@echoes-d62].
