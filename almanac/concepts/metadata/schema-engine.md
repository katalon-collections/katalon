---
title: "Schema Engine"
summary: "The schema engine defines configurable metadata fields for records and vocabulary terms, then drives validation, admin forms, search flags, facets, relation mirroring, and export mappings."
topics: [concepts, metadata, schema, admin]
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
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
  - id: schema-service-tests
    type: file
    path: backend/tests/test_schema_service.py
  - id: pid-service
    type: file
    path: backend/src/katalon/services/pid_service.py
  - id: schema-container-tests
    type: file
    path: backend/tests/integration/test_schema_container_fields.py
  - id: main
    type: file
    path: backend/src/katalon/main.py
  - id: schema-doc
    type: web
    url: https://katalon-collections.github.io/katalon-docs/administration/schema/
  - id: vocabularies-api
    type: file
    path: backend/src/katalon/api/v1/vocabularies.py
  - id: vocabulary-reference-service
    type: file
    path: backend/src/katalon/services/vocabulary_reference_service.py
  - id: record-form-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
---

The schema engine is Katalon's configurable metadata layer. It stores field definitions in `field_definitions`, stores record values in JSONB metadata columns, and lets admins change field structure without adding database columns for each cataloguing field [@models]. The current API accepts schema targets for all seven core record types plus vocabulary terms, validates subtype scope, embeds group sub-fields, soft-deletes fields, and queues reindex work when changes affect indexed document content [@schema-api]. The admin schema screen keeps core field properties and field-type-specific settings visible; its native **Erweiterte Optionen** disclosure contains sort order, visibility flags, portal placement, validation, defaults, locks, AI settings, and metadata export mappings [@schema-screen].

## Field Definitions

A field definition names one metadata field and binds it to a `target_type`. The model includes a multilingual `label`, `field_type`, required and repeatable flags, search and facet flags, sort order, display flags, portal-detail placement (`detail_slot`), an optional detail role (`detail_role`), arbitrary JSONB `settings`, an optional `target_subtype`, and an optional `parent_id` for group sub-fields [@models]. The admin schema editor exposes `sort_order` as a numeric field named "Sortierung" and supports reordering fields by dragging rows in the field list, which persists schema changes through the schema API; `PUT /v1/schema/{target_type}/bulk` also supports grouped field updates [@schema-screen]. Repeatable fields can store an optional integer `settings.max_count`; the schema editor writes it only when repeatability is enabled, and `validate_metadata` rejects saved list values longer than that limit [@schema-screen] [@schema-service]. The repository documentation describes the intended admin workflow: admins create fields in the schema UI, and saved fields become visible in record forms without database migrations [@schema-doc].

Runtime behavior is stricter than a plain JSON editor. The schema API rejects unknown target types, verifies subtype references, blocks nested group fields, validates authority and vocabulary settings, rejects unknown `pid_provider` values on pid fields (`dnb_urn` or `ark`), and prevents deletion of the system `label` and `idno` fields [@schema-api]. Deletion is a soft delete through `is_deleted`, so old JSONB values can remain stored while the field disappears from normal schema reads [@schema-api]. The admin schema field list always pins `idno` and `label` first, marked with a "System" badge, regardless of `sort_order` or drag reordering; their field detail panel drops field type, required/repeatable/translatable, and lock, since those structural settings are fixed and rendered outside the generic Metadaten machinery in ScreenForm's pinned Stammdaten card. `label` is free text, so it keeps validation regex, default value, and AI assist; `idno` is a structured, usually machine-assigned identifier and drops those three as well, leaving only the multilingual label and help text [@schema-screen].

Three field definitions are auto-seeded at application startup rather than through migrations or an admin action, so every installation has them without manual setup. `_ensure_label_fields` creates a required `label` text field for each of the seven primary types if none exists; `_ensure_idno_fields` likewise creates an `idno` text field per primary type. `idno` mirrors the native `idno` model column (see [Field Definitions](#field-definitions) below) rather than storing values in JSONB metadata — the field definition exists solely so its display label stays admin-configurable per language, exactly like `label`. `_ensure_collection_description_field` creates a `richtext` `description` field (`detail_slot: "main"`, `detail_role: "description"`) for `collection` specifically, consumed by the portal collection detail page (rendered below the in-collection search box) and the collection list teasers [@main]. All three checks run on every startup and only insert when no row of that name exists at all for the scope — including soft-deleted ones, since `(target_type, target_subtype, name)` stays globally unique per scope.

Admins can reset a whole primary-type schema or a single subtype schema from the Settings danger zone. The reset soft-deletes active custom field definitions in the selected scope, including group sub-fields, then queues one reindex; it retains the system `label` and `idno` fields and never removes existing record metadata. Recreating a field with the same technical name makes retained values editable again [@schema-api] [@schema-screen].
Field definitions reject malformed regular expressions at configuration time. Values for active fields are validated uniformly on create, update, import, batch, and publish: number and boolean values are typed (with automatic string-to-number coercion for valid numeric strings and empty string handling); free vocabulary values are text and geographic values are WGS84 `{lat, lon, accuracy_m?}` objects; controlled-vocabulary values are `{id, label}` references to a term in the configured vocabulary. Metadata keys without an active field definition remain as legacy data, are neither removed nor validated, and the record form renders them in a separate read-only "Nicht im Schema" section where a curator may remove them explicitly [@schema-api] [@schema-service] [@record-form-screen].


Admins can duplicate existing field definitions directly from the schema field list (three-dots action menu) or from the field detail panel. Duplication generates a collision-free technical name (e.g. `title_copy` or `title_copy_2`), appends `(Kopie)` / `(Copy)` to configured labels, resets any non-reusable `description` detail role back to `none`, and places the new field directly after existing fields. For container fields (`field_type == "group"`), the endpoint (`POST /v1/schema/{field_id}/duplicate`) recursively clones all active sub-fields under the new container with unique sub-field names [@schema-api] [@schema-screen] [@schema-container-tests].

## Moving Unused Fields Between Subtypes

An unused top-level field can move to another subtype of the same primary type
through its `target_subtype`. A group moves together with its active children.
The backend counts usage of the field and children before changing scope and
returns 409 if any stored values would become hidden in the old subtype.
Duplicate into the target scope instead when the field is in use. The API also
checks naming collisions and target subtype existence [@schema-api] [@schema-screen].

## System Fields: `idno` And `label`

Every record also has a database-generated UUID primary key (`id`), independent of the schema engine entirely — it is never user-facing as "the" identifier and carries no cataloguing meaning. `idno` and `label` are the two schema-engine fields that give a record its actual institutional identity and display name, and both stay mandatory by design rather than becoming schema-configurable, a decision revisited against museum/library/archival cataloguing standards rather than assumed:

- **`idno`** ("ID-Nr.", e.g. accession/inventory number or shelfmark) is the record's fachliche/institutional identifier in addition to the UUID — comparable to Spectrum/Object ID's object number, which is "strictly mandatory" for accountability, not to a library's external identifiers (ISBN/ISSN/DOI), which stay optional supplementary metadata even under RDA. Requiring it unconditionally keeps every record traceable to a physical/institutional counterpart. Staff are not necessarily forced to type it by hand: `AdminConfig.idno_schemas`/`idno_patterns` plus `consume_next_idno` let an institution configure an auto-numbering pattern per `target_type`, in which case the create endpoints assign `idno` automatically when left blank.
- **`label`** ("Titel") stays a required field too, but Katalon does not auto-generate a value when a record genuinely has none (e.g. an unlabelled museum object, a geological sample with no proper title). Both RDA (2.3.2.10/2.3.2.11, "devised title") and ISAD(G) (3.1.2 "supplied title") require the cataloguer to formulate a brief descriptive replacement title in that case — conventionally set off in square brackets, e.g. `[Ohne Titel]` or a more descriptive `[Basaltprobe, Fundort X]` — precisely to mark it as supplied rather than taken from the object itself. This is a cataloguing decision, not something the software should synthesize automatically, so the schema engine's `is_required` check on `label` is left enforced as-is; entering a bracketed placeholder title is the expected workflow when no natural title exists.

## Values In Metadata

Primary records keep cataloguing data in a JSONB column named `metadata` on their ORM tables, exposed in Python as `metadata_` [@models]. `validate_metadata` loads active top-level fields for the record type and optional subtype, checks required values, repeatability, text regexes, PID and URL structures, relation structures, relation target existence, authority entry shape and source matching, group instances, and vocabulary-term field constraints [@schema-service] [@schema-service-tests]. `prepare_metadata` applies configured defaults for text, vocab, vocab-free, date, and number fields, coerces numeric strings into typed numbers (and empty values to `None`), preserves or removes locked fields depending on editor permissions, and protects PID fields unconditionally: stored PID values are kept and client-supplied PID input is dropped, so PID fields can only be written by the mint endpoints and publish auto-minting, regardless of role [@schema-service] [@pid-service]. `url` fields store `{value, label}` objects where `value` is a full http(s) URL and `label` is an optional link title; the importer coerces plain URL strings into that shape.

Group fields are repeatable container fields. The database represents the group itself as a `FieldDefinition` row with `field_type == "group"` and each child as another `FieldDefinition` row whose `parent_id` points at the group [@models]. The API returns top-level fields with embedded `children`, blocks recursive groups, and accepts non-group child definitions under a saved group [@schema-api]. The admin UI's fixed sub-field type list is `text`, `richtext`, `date`, `number`, `boolean`, `vocab`, `vocab_free`, `relation`, and `authority`; grouped authority fields use the same enabled-source setting and value validation as ordinary authority fields [@schema-screen] [@schema-service] [@schema-container-tests]. Sub-fields are reordered in the schema editor with up/down buttons, which write `sort_order` for every affected sibling; the portal renders them in that order. The group setting `emphasize_first_child` (checkbox in the group's detail panel) makes the portal show the first sub-field's value bold [@schema-screen].
Deleting a controlled term with active references first returns its usage count. The curator must explicitly choose either a replacement term from the same vocabulary, which updates all configured direct and group-field references before deletion, or a confirmed force deletion. Forced deletion retains the stored UUID and label; the record form marks it as "Term gelöscht" rather than pretending the reference still resolves [@vocabularies-api] [@vocabulary-reference-service] [@record-form-screen]. A term with child terms in the hierarchy is blocked the same way (409, `child_count`) unless the caller passes `cascade=true` (delete the whole subtree, with usage counted atomically across every descendant before any row is removed) or `reparent=true` (move direct children up to the deleted term's own parent) — the self-referential `parent_id` FK's `ondelete=SET NULL` is a database-level fallback only, never a silent default the API relies on [@vocabularies-api] [@vocabulary-reference-service].


## Admin And Search Effects

The schema screen exposes field properties that affect more than form rendering. `show_in_detail` and `show_in_list` tell downstream UI whether a field belongs in detail or list views, `detail_slot` places visible fields in the public detail page's main column or sidebar, and `detail_role` can designate one description field per type/subtype. The schema API rejects duplicate non-`none` detail roles in the same scope. `is_facet` marks fields for faceting and requires `is_public` (the API clears it for non-public fields, because facet values come from the public `facet_all_*` index fields); it is independent of `show_in_detail`, so a field can be a facet without being repeated on the detail page. `is_searchable` controls whether a field should be included in search behavior [@models] [@schema-api] [@schema-screen]. Newly created `label` system fields default to `show_in_detail=false`, since the title is already the detail page heading; existing installations keep their setting. `is_public` is the server-enforced publication boundary: disabled fields remain available to authenticated staff but are removed from anonymous REST and portal responses, public schema reads, search documents and facets, OAI mappings, and IIIF manifests. It also applies to individual group children [@models] [@schema-screen]. Changing that flag queues a type-specific reindex, as do create, delete, and restore operations except for `vocabulary_term` [@schema-api].

Relation fields are part of the schema engine but produce entries in the generic relation graph. They are the editor for structured, field-bound relationships such as an author or a place of creation. A relation field stores target settings such as target type, optional target subtype, relation-type vocabulary, an optional fixed relation type, and inherited target fields in JSONB settings [@schema-screen]. The relation synchronization service later mirrors saved relation-field values into `relations`; the relationships card shows those edges but only creates free additional edges, as explained in [generic relations](../relations/generic-relations) [@schema-service].

## Field Deletion, Retention, And Hard Delete

Deleting a schema field is a soft delete by default (`is_deleted = True`), preserving field integrity and leaving values in existing records readable as historical ("not in schema") data if `purge_data=False` was selected. Soft-deleted fields reserve their `internal_name` under the unique database constraint.

The Admin UI provides a recycle bin view (`include_deleted=True` in `GET /v1/schema`) where deleted fields can be inspected and managed:
- **Restoration (`POST /v1/schema/{field_id}/restore`)**: Restores a soft-deleted field. Restoring a group container atomically restores its soft-deleted subfields. Restoring an orphaned subfield whose parent container is still deleted is blocked (422) until the parent is restored. Unique `detail_role` rules and naming conflicts are validated prior to restoration.
- **Hard Delete (`DELETE /v1/schema/{field_id}/hard`)**: Administrators can physically delete a soft-deleted field row from PostgreSQL, permanently releasing the `internal_name`. Hard delete is blocked (409) if the field or any of its container children still has data in records (`usage_count > 0`), requiring data to be purged or cleaned beforehand. System fields cannot be hard deleted.

## Vocabulary Terms

Vocabulary terms use the same `field_definitions` table with `target_type == "vocabulary_term"` and the vocabulary UUID as `target_subtype` [@schema-api]. The API limits vocabulary-term custom fields to `text`, `number`, `boolean`, and `authority`, and the admin screen switches its field-type list when the active target is vocabulary terms [@schema-api] [@schema-screen]. This ties the schema engine to [vocabularies](vocabularies) without creating a second metadata system for term-level custom data.

## Form Variants

Field definitions are the field catalog; they say nothing about which subset a given form shows or in what order. That layer is `FormVariant` (#275): a named, ordered selection of existing field names per `target_type`/`target_subtype`, with optional role-based and global defaults, resolved client-side in [Schema Driven Record Forms](../../architecture/workflows/schema-driven-record-forms). No new field data is introduced — deleting or renaming the underlying `FieldDefinition` is still the schema engine's concern.

## Related Pages

Read [vocabularies](vocabularies) for controlled terms and relation-type vocabularies, [record subtypes](record-subtypes) for the subtype scope that field definitions use, and [generic relations](../relations/generic-relations) for relation fields after they are mirrored into the relation table.
