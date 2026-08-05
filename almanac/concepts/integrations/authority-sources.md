---
title: "Authority Sources"
summary: "Authority sources register external lookup adapters for normalized identifiers, expose authenticated search and fetch endpoints, and feed authority fields in records and vocabulary-term metadata."
topics: [concepts, authority, integrations, metadata]
sources:
  - id: authority-contract
    type: file
    path: backend/src/katalon/integrations/authority.py
  - id: authority-service
    type: file
    path: backend/src/katalon/services/authority_service.py
  - id: authority-api
    type: file
    path: backend/src/katalon/api/v1/authority.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: main
    type: file
    path: backend/src/katalon/main.py
  - id: schema-api
    type: file
    path: backend/src/katalon/api/v1/schema_admin.py
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: authority-input
    type: file
    path: frontend/admin/src/components/AuthorityInput.tsx
  - id: schema-service
    type: file
    path: backend/src/katalon/services/schema_service.py
  - id: schema-service-tests
    type: file
    path: backend/tests/test_schema_service.py
  - id: schema-container-tests
    type: file
    path: backend/tests/integration/test_schema_container_fields.py
  - id: vocab-decision
    type: file
    path: .agents/knowledge/decisions/vocabulary-custom-fields.md
  - id: gnd-adapter
    type: file
    path: backend/src/katalon/integrations/gnd_adapter.py
  - id: geonames-adapter
    type: file
    path: backend/src/katalon/integrations/geonames_adapter.py
  - id: viaf-adapter
    type: file
    path: backend/src/katalon/integrations/viaf_adapter.py
  - id: wikidata-adapter
    type: file
    path: backend/src/katalon/integrations/wikidata_adapter.py
  - id: tgn-adapter
    type: file
    path: backend/src/katalon/integrations/tgn_adapter.py
  - id: iconclass-adapter
    type: file
    path: backend/src/katalon/integrations/iconclass_adapter.py
  - id: dnb-urn
    type: file
    path: backend/src/katalon/integrations/dnb_urn_adapter.py
---

Authority sources are Katalon's adapter system for searching external authority files and storing normalized authority references in metadata. The shared integration contract defines `AuthorityHit` with `source`, `external_id`, `label`, `description`, and `extra`, and every authority adapter implements asynchronous `search` and `fetch` methods [@authority-contract]. Built-in adapters cover GND, GeoNames, VIAF, Wikidata, TGN, and ICONCLASS, while the database can register enabled sources and custom adapter classes through the `authority_sources` table [@authority-service] [@models].

## Registry And Startup Defaults

The runtime registry starts with built-in adapter instances for `gnd`, `geonames`, `viaf`, `wikidata`, `tgn`, and `iconclass` [@authority-service]. On startup, Katalon inserts default `authority_sources` rows for the same six sources when missing; GND is enabled by default and the other built-in sources are initially disabled [@main]. Each database row stores an id, label, adapter class path, JSONB config, and enabled flag [@models].

Enabled database rows can override built-in adapter attributes through their config. For non-built-in ids, the service imports `adapter_class`, instantiates it with config, and adds it to the registry; import failures are ignored, and if registry loading fails entirely the service falls back to built-ins [@authority-service]. The service caches the loaded registry and exposes `invalidate_cache` for callers that change source configuration [@authority-service].

## API Surface

The authority API requires a current user for source listing, search, and fetch [@authority-api]. `GET /authorities/` returns configured database sources, or built-in source ids as uppercase labels when the table has no rows [@authority-api]. `GET /authorities/search` and `GET /authorities/fetch` call the registry, return `AuthorityHit` data, reject unknown sources with 404, and apply a `60/minute` rate limit [@authority-api].

The schema admin API validates authority field settings against enabled sources. When a field has `field_type == "authority"`, its `settings.source` must name an enabled database source, or a built-in source when no database source rows exist [@schema-api]. That validation connects authority registration to the [schema engine](../metadata/schema-engine) rather than letting forms store arbitrary source ids.

## Built-In Adapters

The adapter directory contains concrete adapters for GND, GeoNames, VIAF, Wikidata, TGN, and ICONCLASS, each declaring a `source_id` and implementing `search` and `fetch` methods that return the shared `AuthorityHit` shape [@gnd-adapter] [@geonames-adapter] [@viaf-adapter] [@wikidata-adapter] [@tgn-adapter] [@iconclass-adapter]. Wikidata builds a custom User-Agent from Katalon's base URL and contact configuration before calling Wikidata APIs [@wikidata-adapter]. The DNB URN adapter is separate from the authority source contract: it talks to the configured DNB URN API for namespace suggestions and URN creation, but it does not subclass `AuthoritySource` or appear in the authority registry [@dnb-urn] [@authority-service].

## Metadata Use

Authority fields are available in the schema UI as a field type with a selectable enabled authority source [@schema-screen]. Record forms render top-level authority fields through the shared `AuthorityInput` component, which searches the selected source, supports keyboard listbox navigation, and stores `{source, external_id, label}` when a hit is picked [@screen-form] [@authority-input]. Vocabulary-term custom metadata also supports authority fields, which lets [vocabularies](../metadata/vocabularies) store structured external references using the same source registry as record metadata [@schema-api]. The local vocabulary metadata decision records the intended structured form for authority values as `{source, external_id, label}` and explains why term metadata reuses the existing authority system instead of creating a vocabulary-only mechanism [@vocab-decision].

Authority is also allowed as a group sub-field. `SUB_FIELD_TYPES` includes `authority`, the sub-field editor requires an enabled configured source before saving, and existing authority sub-fields show a warning that changing the source invalidates already stored authority values [@schema-screen]. `ScreenForm` renders authority children with the same `AuthorityInput` component as top-level authority fields, so grouped and ordinary authority metadata share the stored value shape [@screen-form] [@authority-input].

Backend metadata validation checks authority values for ordinary record fields, repeatable authority fields, and authority children inside group instances. The validator requires non-empty `source`, `external_id`, and `label` strings and rejects values whose `source` differs from the field's configured `settings.source`; unit and integration tests cover top-level authority validation, grouped authority validation, and creating an authority sub-field under a group [@schema-service] [@schema-service-tests] [@schema-container-tests].

## Related Pages

Read [schema engine](../metadata/schema-engine) for authority field validation and [vocabularies](../metadata/vocabularies) for authority metadata on vocabulary terms.
