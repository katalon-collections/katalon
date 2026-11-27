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
  - id: authority-api-tests
    type: file
    path: backend/tests/integration/test_authority_sources_api.py
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
  - id: aat-adapter
    type: file
    path: backend/src/katalon/integrations/aat_adapter.py
  - id: dnb-urn
    type: file
    path: backend/src/katalon/integrations/dnb_urn_adapter.py
  - id: settings-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
---

Authority sources are Katalon's adapter system for searching external authority files and storing normalized authority references in metadata. The shared integration contract defines `AuthorityHit` with `source`, `external_id`, `label`, `description`, and `extra`, and every authority adapter implements asynchronous `search` and `fetch` methods [@authority-contract]. Built-in adapters cover GND (plus two GND variants scoped by entity type), GeoNames, VIAF, Wikidata, Getty TGN, ICONCLASS, and Getty AAT, while the database can register enabled sources and custom adapter classes through the `authority_sources` table [@authority-service] [@models].

## Registry And Startup Defaults

The runtime registry starts with built-in adapter instances for `gnd`, `gnd-person`, `gnd-subject`, `geonames`, `viaf`, `wikidata`, `tgn`, `iconclass`, and `aat` [@authority-service]. On startup, Katalon inserts default `authority_sources` rows for the same nine sources when missing; GND (`gnd`, unfiltered) is enabled by default and the other built-in sources — including the two scoped GND variants — are initially disabled [@main]. Each database row stores an id, label, adapter class path, JSONB config, and enabled flag [@models].

`gnd-person` and `gnd-subject` reuse `GNDAdapter` with a constructor-level `filter_type` (a lobid `filter` query value) and matching `source_id`: `gnd-person` restricts search results to `type:Person` (matches both `DifferentiatedPerson` and `UndifferentiatedPerson` records, since both carry the parent `Person` type in lobid's `type` array), `gnd-subject` to `type:SubjectHeading`. `gnd` itself passes no filter and keeps searching the full GND dataset unchanged, so existing fields configured with `gnd` are unaffected. Schema authors pick the scoped variant per field — e.g. `gnd-person` for entity authority fields, `gnd-subject` for vocabulary-term authority fields — the same way they already choose between `gnd`, `viaf`, and `wikidata` [@gnd-adapter] [@schema-screen].

The registry always starts from all builtins, then applies every DB row: rows with `is_enabled = false` are removed from the registry (their built-in stays unregistered, so search/fetch treat the id as unknown), and enabled rows either patch a built-in adapter's attributes from `config` or, for non-built-in ids, dynamically import `adapter_class`, instantiate it with `config`, and add it to the registry; import failures are logged and skipped, and if registry loading fails entirely the service falls back to all-builtins-enabled [@authority-service]. Every lookup reads the current database rows and creates fresh adapter instances. There is no process-local registry cache, so an enable/disable change committed by one API worker is visible to the next lookup in any worker. Removing a config override restores the built-in default instead of retaining an attribute from a previous lookup. Registry reads use an isolated database session so they also work outside the API event loop [@authority-service].

## Admin Management

Admins toggle sources under Settings → Normdatenquellen, which lists every built-in source (merging DB overrides with defaults for sources that have no DB row yet), shows an enable/disable switch per row, and offers a "Verbindung testen" button that issues a source-specific live search. The displayed test request is linked to the source's public search, and success or the raw error appears inline [@settings-screen]. GeoNames API status payloads, such as a missing account or exhausted credits, are reported as errors rather than misleading empty result lists; Getty TGN and AAT use HTTPS for SPARQL and detail lookups [@geonames-adapter] [@tgn-adapter] [@aat-adapter]. Toggling calls `PATCH /authorities/{id}`, which upserts an `authority_sources` row (creating one with default label/adapter class on first toggle) and commits the change before returning, so the next registry lookup sees it [@authority-api] [@authority-service]. The endpoint requires the `admin` role [@authority-api].

## API Surface

The authority API requires a current user for source listing, search, and fetch [@authority-api]. `GET /authorities/` returns the union of the built-in catalog and every row in `authority_sources` — including sources that only exist as a database row with a custom `adapter_class` and no built-in counterpart — using each source's DB row when one exists and falling back to its default label/`is_enabled = true` otherwise [@authority-api]. `PATCH /authorities/{id}` looks up the DB row first and only 404s when the id is neither an existing row nor a built-in id, so DB-only custom sources can be toggled the same way as built-ins [@authority-api] [@authority-api-tests]. `GET /authorities/search` and `GET /authorities/fetch` call the registry, return `AuthorityHit` data, reject unknown or disabled sources with 404, translate adapter-side network errors (`httpx.HTTPError`) into a 502 with a German message instead of an unhandled 500, and apply a `60/minute` rate limit [@authority-api].

`AuthorityInput` also debounces live search on the client: it waits 300 ms after the query changes, clears the previous timer, and does not search before the trimmed query has at least two characters [@authority-input]. There is no shared response cache for external `search()` or `fetch()` calls. Each lookup also reads the small authority registry from the database; this adds one database connection/query before the external request and avoids stale source configuration across API workers [@authority-service]. If external provider rate limits become a real incident, the natural place for a Redis-backed response cache is the authority service choke point, not the individual form components or adapters.

The schema admin API validates authority field settings against enabled sources. When a field has `field_type == "authority"`, its `settings.source` must name an enabled database source, or a built-in source when no database source rows exist [@schema-api]. That validation connects authority registration to the [schema engine](../metadata/schema-engine) rather than letting forms store arbitrary source ids.

## Built-In Adapters

The adapter directory contains concrete adapters for GND, GeoNames, VIAF, Wikidata, Getty TGN, ICONCLASS, and Getty AAT, each declaring a `source_id` and implementing `search` and `fetch` methods that return the shared `AuthorityHit` shape [@gnd-adapter] [@geonames-adapter] [@viaf-adapter] [@wikidata-adapter] [@tgn-adapter] [@iconclass-adapter] [@aat-adapter]. ICONCLASS searches its JSON `/api/search` endpoint, excludes the established top-level categories `1` and `9`, loads candidate labels, and ranks exact, prefix, word, and substring matches before notation depth; the exclusion remains an adapter constant until source configuration exposes it [@iconclass-adapter]. Getty AAT mirrors the TGN adapter: it queries the `vocab.getty.edu` SPARQL endpoint filtered to `skos:inScheme <http://vocab.getty.edu/aat/>` for search and fetches `{id}.json` for detail lookups, preferring German `skos:prefLabel` values [@aat-adapter]. Wikidata builds a custom User-Agent from Katalon's base URL and contact configuration before calling Wikidata APIs [@wikidata-adapter]. The DNB URN adapter is separate from the authority source contract: it talks to the configured DNB URN API for namespace suggestions and URN creation, but it does not subclass `AuthoritySource` or appear in the authority registry [@dnb-urn] [@authority-service].

## Metadata Use

Authority fields are available in the schema UI as a field type with a selectable enabled authority source [@schema-screen]. Record forms render top-level authority fields through the shared `AuthorityInput` component, which searches the selected source, supports keyboard listbox navigation, and turns saved entries from built-in sources into external links. GeoNames picks also persist validated `{lat, lng}` coordinates alongside `{source, external_id, label}`, so the admin form and public portal can expose a toggleable OpenStreetMap embed without an unauthenticated authority lookup; existing GeoNames references gain a map when they are selected again [@screen-form] [@authority-input]. Vocabulary-term custom metadata also supports authority fields, which lets [vocabularies](../metadata/vocabularies) store structured external references using the same source registry as record metadata [@schema-api]. The local vocabulary metadata decision records the intended structured form for authority values as `{source, external_id, label}` and explains why term metadata reuses the existing authority system instead of creating a vocabulary-only mechanism [@vocab-decision].

Authority is also allowed as a group sub-field. `SUB_FIELD_TYPES` includes `authority`, the sub-field editor requires an enabled configured source before saving, and existing authority sub-fields show a warning that changing the source invalidates already stored authority values [@schema-screen]. `ScreenForm` renders authority children with the same `AuthorityInput` component as top-level authority fields, so grouped and ordinary authority metadata share the stored value shape [@screen-form] [@authority-input].

Portal detail pages link every entry of an authority, URL or PID field separately, including repeatable fields (`linkedValues` in `DetailPageLayout.tsx`, `externalHref` in `renderFieldValue.ts`). Fields marked as facet render search links instead.

Backend metadata validation checks authority values for ordinary record fields, repeatable authority fields, and authority children inside group instances. The validator requires non-empty `source`, `external_id`, and `label` strings and rejects values whose `source` differs from the field's configured `settings.source`; unit and integration tests cover top-level authority validation, grouped authority validation, and creating an authority sub-field under a group [@schema-service] [@schema-service-tests] [@schema-container-tests].

## Related Pages

Read [schema engine](../metadata/schema-engine) for authority field validation and [vocabularies](../metadata/vocabularies) for authority metadata on vocabulary terms.
