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
  - id: schema-container-tests
    type: file
    path: backend/tests/integration/test_schema_container_fields.py
  - id: schema-doc
    type: file
    path: docs/02_schema_verwaltung.md
---

The schema engine is Katalon's configurable metadata layer. It stores field definitions in `field_definitions`, stores record values in JSONB metadata columns, and lets admins change field structure without adding database columns for each cataloguing field [@models]. The current API accepts schema targets for objects, entities, places, occurrences, procedures, and vocabulary terms, validates subtype scope, embeds group sub-fields, soft-deletes fields, and queues reindex work for create, delete, restore, and facet-flag changes [@schema-api]. The admin schema screen keeps core field properties and field-type-specific settings visible; its native **Erweiterte Optionen** disclosure contains sort order, visibility flags, portal placement, validation, defaults, locks, AI settings, and metadata export mappings [@schema-screen].

## Field Definitions

A field definition names one metadata field and binds it to a `target_type`. The model includes a multilingual `label`, `field_type`, required and repeatable flags, search and facet flags, sort order, display flags, portal-detail placement (`detail_slot`), an optional detail role (`detail_role`), arbitrary JSONB `settings`, an optional `target_subtype`, and an optional `parent_id` for group sub-fields [@models]. The admin schema editor exposes `sort_order` as a numeric field named "Sortierung" and supports reordering fields by dragging rows in the field list, which persists the new order via sequential `PUT` requests since the API has no bulk-reorder endpoint [@schema-screen]. The repository documentation describes the intended admin workflow: admins create fields in the schema UI, and saved fields become visible in record forms without database migrations [@schema-doc].

Runtime behavior is stricter than a plain JSON editor. The schema API rejects unknown target types, verifies subtype references, blocks nested group fields, validates authority and vocabulary settings, and prevents deletion of the system `label` field [@schema-api]. Deletion is a soft delete through `is_deleted`, so old JSONB values can remain stored while the field disappears from normal schema reads [@schema-api].

Admins can reset a whole primary-type schema or a single subtype schema from the Settings danger zone. The reset soft-deletes active custom field definitions in the selected scope, including group sub-fields, then queues one reindex; it retains the system `label` field and never removes existing record metadata. Recreating a field with the same technical name makes retained values editable again [@schema-api] [@schema-screen].

## Values In Metadata

Primary records keep cataloguing data in a JSONB column named `metadata` on their ORM tables, exposed in Python as `metadata_` [@models]. `validate_metadata` loads active top-level fields for the record type and optional subtype, checks required values, repeatability, text regexes, PID structures, relation structures, relation target existence, authority entry shape and source matching, group instances, and vocabulary-term field constraints [@schema-service] [@schema-service-tests]. `prepare_metadata` applies configured defaults for text, vocab, vocab-free, date, and number fields, and it preserves or removes locked fields depending on editor permissions [@schema-service].

Group fields are repeatable container fields. The database represents the group itself as a `FieldDefinition` row with `field_type == "group"` and each child as another `FieldDefinition` row whose `parent_id` points at the group [@models]. The API returns top-level fields with embedded `children`, blocks recursive groups, and accepts non-group child definitions under a saved group [@schema-api]. The admin UI's fixed sub-field type list is `text`, `date`, `number`, `boolean`, `vocab`, `vocab_free`, `relation`, and `authority`; grouped authority fields use the same enabled-source setting and value validation as ordinary authority fields [@schema-screen] [@schema-service] [@schema-container-tests].

## Admin And Search Effects

The schema screen exposes field properties that affect more than form rendering. `show_in_detail` and `show_in_list` tell downstream UI whether a field belongs in detail or list views, `detail_slot` places visible fields in the public detail page's main column or sidebar, and `detail_role` can designate one description field per type/subtype. The schema API rejects duplicate non-`none` detail roles in the same scope. `is_facet` marks fields for faceting, and `is_searchable` controls whether a field should be included in search behavior [@models] [@schema-api] [@schema-screen]. `is_public` is the server-enforced publication boundary: disabled fields remain available to authenticated staff but are removed from anonymous REST and portal responses, public schema reads, search documents and facets, OAI mappings, and IIIF manifests. It also applies to individual group children [@models] [@schema-screen]. Changing that flag queues a type-specific reindex, as do create, delete, and restore operations except for `vocabulary_term` [@schema-api].

Relation fields are part of the schema engine but produce entries in the generic relation graph. They are the editor for structured, field-bound relationships such as an author or a place of creation. A relation field stores target settings such as target type, optional target subtype, relation-type vocabulary, an optional fixed relation type, and inherited target fields in JSONB settings [@schema-screen]. The relation synchronization service later mirrors saved relation-field values into `relations`; the relationships card shows those edges but only creates free additional edges, as explained in [generic relations](../relations/generic-relations) [@schema-service].

## Vocabulary Terms

Vocabulary terms use the same `field_definitions` table with `target_type == "vocabulary_term"` and the vocabulary UUID as `target_subtype` [@schema-api]. The API limits vocabulary-term custom fields to `text`, `number`, `boolean`, and `authority`, and the admin screen switches its field-type list when the active target is vocabulary terms [@schema-api] [@schema-screen]. This ties the schema engine to [vocabularies](vocabularies) without creating a second metadata system for term-level custom data.

## Form Variants

Field definitions are the field catalog; they say nothing about which subset a given form shows or in what order. That layer is `FormVariant` (#275): a named, ordered selection of existing field names per `target_type`/`target_subtype`, with optional role-based and global defaults, resolved client-side in [Schema Driven Record Forms](../../architecture/workflows/schema-driven-record-forms). No new field data is introduced — deleting or renaming the underlying `FieldDefinition` is still the schema engine's concern.

## Related Pages

Read [vocabularies](vocabularies) for controlled terms and relation-type vocabularies, [record subtypes](record-subtypes) for the subtype scope that field definitions use, and [generic relations](../relations/generic-relations) for relation fields after they are mirrored into the relation table.
