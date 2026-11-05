---
title: "Generic Relations"
summary: "Generic relations store typed links between records in one relation table; schema fields maintain structured edges while the relationship card adds free extras."
topics: [concepts, relations, records, metadata]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: schema-api
    type: file
    path: backend/src/katalon/api/v1/schema_admin.py
  - id: schema-service
    type: file
    path: backend/src/katalon/services/schema_service.py
  - id: relation-service
    type: file
    path: backend/src/katalon/services/relation_service.py
  - id: relation-api
    type: file
    path: backend/src/katalon/api/v1/relations.py
  - id: relation-type-service
    type: file
    path: backend/src/katalon/services/relation_type_service.py
  - id: vocab-api
    type: file
    path: backend/src/katalon/api/v1/vocabularies.py
  - id: relation-list
    type: file
    path: frontend/portal/src/components/RelationsList.tsx
  - id: related-objects
    type: file
    path: frontend/portal/src/components/RelatedObjects.tsx
  - id: portal-detail-layout
    type: file
    path: frontend/portal/src/components/DetailPageLayout.tsx
  - id: relation-field-row
    type: file
    path: frontend/portal/src/components/RelationFieldRow.tsx
  - id: relation-type-labels
    type: file
    path: frontend/portal/src/hooks/useRelationTypeLabels.ts
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
  - id: screen-form
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: admin-client
    type: file
    path: frontend/admin/src/api/client.ts
  - id: dependencies
    type: file
    path: backend/src/katalon/core/dependencies.py
  - id: portal-public-api
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
  - id: public-metadata-service
    type: file
    path: backend/src/katalon/services/public_metadata_service.py
---

Generic relations are Katalon's shared graph table for links between records. A `Relation` row stores `from_type`, `from_id`, `to_type`, `to_id`, a string `relation_type`, JSONB relation metadata, a schema-derived flag, and creation time [@models]. The same table holds direct relations created through the relation API and relations mirrored from schema relation fields, so object, entity, place, occurrence, collection, and procedure links can be queried through one surface [@relation-api] [@relation-service].

## Relation Rows

The relation table does not use foreign keys to every possible record table. Instead, each endpoint is stored as a type string plus UUID pair, with indexes on `(from_type, from_id)` and `(to_type, to_id)` for directional lookup [@models]. This design fits Katalon's multi-type record model because a relation can connect any supported record type pair without adding a join table per pair.

To prevent dangling or invalid relation links, `validate_relation_endpoint` enforces integrity before creating manual relations: both endpoints must exist in their respective tables and must not be marked as deleted (`deleted_at is None`) [@relation-api] [@relation-service]. Schema relation synchronization (`sync_schema_relations`) similarly verifies targets and filters out missing or soft-deleted records before recreating mirrored relation rows [@relation-service].

The relation API requires an authenticated caller for every route, creates manual relations, updates `relation_type` or metadata, and deletes relation rows [@relation-api]. Create, update, and delete operations require the `manage_content` capability, which is assigned to catalogers, editors, admins, and superusers. Listing only requires authentication, but filters its result set: a relation is dropped entirely unless the caller has record-read permission on *both* `from_type` and `to_type`, using the same per-type `has_record_permission()` check other record endpoints use — an authorized endpoint must never leak a linked record's id, type, or label through the unauthorized side of a relation [@relation-api] [@dependencies].
## Display Labels

Both list endpoints (`GET /v1/relations` for the admin API, `GET /portal/v1/relations` for the public one) resolve a `from_label`/`to_label` pair for every row server-side instead of returning bare `from_id`/`to_id` UUIDs for callers to look up themselves [@relation-api] [@portal-public-api]. `resolve_relation_labels` batches the referenced records by type, extracts a display title the same way search indexing does (checked field names, first repeatable-field entry, `idno` fallback), and returns `None` when a referenced record is missing or, for the portal caller, no longer public [@relation-service]. The portal call additionally passes `public_only=True`, which projects each record's metadata through the same public-field filter as public record reads before extracting a title, and restricts the lookup to public statuses [@relation-service] [@public-metadata-service]. `None` here means "endpoint gone", distinct from a resolvable record whose title happens to be empty (which still falls back to `idno`).

A `None` label is a different situation from a relation being excluded from the portal response entirely: the portal endpoint's existing `_public_endpoint_clause` filter already drops any relation where either endpoint isn't a public record, so a non-public target never reaches label resolution in the first place — that's a permission decision, not a display bug [@portal-public-api]. A `None` label on a row the endpoint *did* return means the target existed and was public/accessible at query time but has since been deleted.

Because labels now come resolved from the API, the admin relationships panel and the portal `RelationsList` no longer need to fetch every relation target record individually to build a title map — they read `r.from_label`/`r.to_label` directly and fall back to "Nicht verfügbar" / `common.recordUnavailable` when a label is `None`, never a raw UUID [@screen-form] [@relation-list].

## Admin Picker And Inline Creation

The relationships card on every saved record is the complete, bidirectional graph overview. It groups field-bound edges separately and directs their editing back to the matching schema field. Its add action is for free relationships to other primary record types, including the source record's own type. After choosing the target type, the user chooses a relation type and either selects a search result or opens the schema-driven quick-create dialog [@screen-form]. An exact duplicate of target id and relation type is rejected in the form against the relations already loaded for the record [@screen-form]; another relation type to the same target remains valid. Viewers do not see the create action. The server independently rejects a duplicate `create_relation` call the same way. Object-to-collection membership is the one exception routed outside this generic picker: the object form renders a dedicated "Sammlung" select that creates, updates, or deletes a single `member_of` relation (`object` → `collection`) alongside the record save, instead of going through the free-relationship add flow [@screen-form].

Quick creation first saves the target as a draft through its ordinary record endpoint. The relationships panel then creates the relation row immediately. If that second request fails, the new draft remains selected and the picker offers `Erneut verknüpfen` instead of deleting the draft [@screen-form] [@admin-client].

## Schema-Derived Relations

Schema relation fields are stored in record metadata but mirrored into the relation table. `sync_schema_relations` deletes prior schema-derived rows for the source record, loads top-level relation fields and relation sub-fields inside group fields, and creates fresh `Relation` rows from current metadata values [@relation-service]. Mirrored rows set `is_schema_derived` and record their source field in relation metadata, using `group.field` syntax for relation sub-fields inside groups [@relation-service]. Only fields without a subtype or with the record's own subtype are mirrored (the subtype is read from the record unless the caller passes it; a record without subtype only gets fields without one), and at most one row per target, relation type and source field is written. Before 1.49.0 the sync ignored the subtype, so equally named fields of different subtypes (for example `expression` on work and manifestation) wrote identical rows. `katalon-manage resync-schema-relations [--dry-run]` reports those duplicates and rebuilds all schema-derived rows; the real run is a data change and needs the operator's approval and a backup, and it does not reindex [@relation-service].

The schema editor warns, without blocking, when a relation field X → Y is edited while a field Y → X already exists (`POST /v1/schema/relation-counterparts`, `find_counter_direction_relation_fields`). A `NULL` subtype on either side counts as "all subtypes", group sub-fields count, soft-deleted fields and the edited field itself do not. The hint exists because both fields are maintained independently and drift apart, while incoming relations already appear in the portal block "Verknüpfungen" with the relation type's inverse label [@schema-api] [@schema-service].

Before recreating schema-derived rows, the sync also loads the source record's existing manual (non-schema-derived) relations and skips recreating any schema-derived row that would duplicate one of them on `(to_type, to_id, relation_type)`. This matters specifically for relation fields whose type is chosen per-instance via `settings.relation_type_vocab` rather than a single `fixed_relation_type` — a curator can pick the identical target and relation type once through the free relationships card and again through such a field (including inside a repeatable group), and without this check both paths would otherwise create separate rows for the same edge [@relation-service].

This mirror keeps form-oriented metadata and graph-oriented relation queries aligned. A cataloguer can work through a field configured by the [schema engine](../metadata/schema-engine), while portal and workflow code can read from `relations` without re-parsing every record's JSONB metadata.

This also defines the save boundary for inline creation. A schema relation field keeps the selected draft in the source form's local metadata until the source record is saved and `sync_schema_relations` runs. This quick-create action is also available inside a quick-create form for every primary target type. The general relationships panel works on an already saved source record and writes its relation row immediately [@screen-form] [@relation-service].

## Relation Types And Inverse Labels

Relation fields can point at a relation-type vocabulary through `settings.relation_type_vocab` and can optionally select one fixed term from it [@schema-screen]. A fixed type makes the field the unambiguous editor for that semantic relationship; without one, the form offers the vocabulary choices. Relation-type vocabularies are ordinary vocabularies with `kind == "relation"`, and vocabulary terms include `inverse_label` JSONB for labels shown from the opposite direction [@models]. The relation itself stores only the relation type code; label resolution happens outside the relation row.

Relation-type vocabularies are always flat: their terms cannot have parent links. They can narrow a term to allowed source and target record types with `VocabularyTerm.applies_from` and `VocabularyTerm.applies_to`, where an empty list means unrestricted for that side [@models]. The vocabulary terms endpoint applies the same rule when called with `from_type` and `to_type`, and the relation API validates create and update requests against relation vocabulary terms before writing the row [@vocab-api] [@relation-api] [@relation-type-service]. If no relation vocabulary term exists for a relation type, the service treats that code as unrestricted, preserving legacy free-text relation types and imported relation rows [@relation-type-service].

The Admin relation picker passes the current source record type and chosen target type into the vocabulary endpoint before showing relation-type choices [@screen-form] [@admin-client]. That keeps the dropdown from offering known-disallowed relation types, while the server remains the final authority and returns HTTP 422 for a relation vocabulary term that does not apply to the requested pair [@relation-api] [@relation-type-service].

The portal relation list receives a `resolveLabel` callback and passes it the relation type plus direction flag, so the display layer can choose the forward or inverse label for the current record [@relation-list]. The same component computes the other endpoint from the current record ID and navigates to a type-specific portal path [@relation-list].

Schema relation fields shown inside portal detail metadata use a narrower path: `DetailPageLayout` loads relation-type vocabulary terms through `useRelationTypeLabels` and passes a code-to-label resolver into `RelationFieldRow`, so relation field values show localized labels next to target links instead of exposing raw `relation_type` codes [@portal-detail-layout] [@relation-field-row] [@relation-type-labels]. This resolver has no direction argument there because schema relation field values describe the source field's forward relation, unlike the bidirectional generic relation list [@relation-field-row] [@relation-list]. When a relation field configures `settings.inherited_fields`, `RelationFieldRow` resolves the target record's public metadata and renders those inherited field values with localized labels directly under the relation field entry; when the field targets `place` and has `settings.show_place_map` enabled, it additionally renders an embedded `GeoMap` below the entry whenever the linked place has coordinates (`lat`/`lon`) [@schema-screen] [@portal-detail-layout] [@relation-field-row].

Like vocabulary values, a relation field entry's name links to a pre-filtered search when a facet covers it: the field itself if it is a relation facet, else a configured relation facet of the record type matching the entry's relation type (outgoing). A small secondary link then opens the target record; without a matching facet the name links to the record as before [@portal-detail-layout] [@relation-field-row].

Relation field values carry the target's label in record metadata, so the public projection checks targets before such a value leaves the authenticated API. `load_hidden_relation_targets` collects the ids in relation fields and relation sub-fields of groups and returns those whose target is missing, soft-deleted or not in a public status; `filter_public_metadata` then drops these entries, and drops relation field values entirely when the caller passed no such set (fail closed) [@public-metadata-service]. Public record reads (`project_public_record`), the search index document, inherited fields, the export context (OAI/LIDO) and the IIIF manifest metadata pass the checked set; callers that only extract a title keep the plain projection [@public-metadata-service].

`GET /portal/v1/relations` returns `source_field` for schema-derived rows. The object, entity, place and occurrence pages leave outgoing relations out of the generic relation list when a shown top-level field (or group) of the current record is their source, so a link edited in a relation field appears once, as the field row [@portal-public-api] [@relation-list].

Entity, place, and occurrence pages show each linked object once as a card, even when several relation rows connect it to the current record. Cards list their distinct directional relation labels. When the cards use more than one relation type, the portal offers local relation-type chips with the number of matching unique objects; their counts can overlap because one object may have several relation types. The chips filter the already loaded cards without another API request and resolve each directional label with the same vocabulary data [@related-objects].

## Procedure Rule

Generic relations also carry workflow constraints. When creating a relation between a procedure and an object, the relation API checks whether the procedure is an active `loan_out`; if so, it rejects a second active loan-out relation for the same object with HTTP 409 [@relation-api]. The helper that finds active loans joins procedures through the relation table in either direction, which keeps the rule independent of relation direction [@relation-service].

## Related Pages

Read [schema engine](../metadata/schema-engine) for relation field configuration and [vocabularies](../metadata/vocabularies) for relation-type vocabularies and inverse labels.
