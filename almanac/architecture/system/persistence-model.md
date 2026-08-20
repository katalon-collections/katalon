---
title: "Persistence Model"
summary: "Katalon stores fixed record shells in PostgreSQL tables and keeps configurable metadata, settings, audit records, and snapshots in JSONB-backed structures."
topics: [architecture, persistence, metadata, audit, search]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: initial-migration
    type: file
    path: backend/migrations/versions/0001_initial.py
  - id: version-migration
    type: file
    path: backend/migrations/versions/0027_record_version.py
  - id: media-reference-migration
    type: file
    path: backend/migrations/versions/0038_media_import_references.py
---

Katalon's persistence model uses PostgreSQL as the durable system of record, with separate ORM tables for record classes and JSONB columns for configurable metadata. Objects, entities, places, occurrences, and procedures all have stable columns for identity, status, timestamps, and search state, while user-defined fields live in the `metadata` JSONB column [@models]. The initial migration creates PostGIS and `pg_trgm` extensions, then builds the primary tables and supporting tables for users, schema definitions, vocabularies, relations, media, audit logs, snapshots, and authority sources [@initial-migration].

## Record Tables And JSONB

The core record tables are not one generic table. `Object`, `Entity`, `Place`, `Occurrence`, and `Procedure` each have their own table and own type-specific columns, but all carry `metadata_ = mapped_column("metadata", JSONB, default=dict)` for dynamic fields [@models]. This gives the API and frontend a stable record shell while allowing the schema engine to define fields without database migrations for every collection-specific metadata change.

PostgreSQL indexes are tuned around that split. The ORM defines GIN indexes on metadata for the primary record tables, and places also define a GiST index on `geom` [@models]. The initial migration creates PostGIS, creates the `places.geom` geometry column as `geometry(Point, 4326)`, and adds the same GiST index [@initial-migration].

## Schema And Controlled Values

`FieldDefinition` records describe dynamic fields by target type, optional subtype, name, localized label, field type, required and repeatable flags, search/display flags, settings, deletion flag, and optional parent field for grouped fields [@models]. `Vocabulary` and `VocabularyTerm` store controlled values, labels, inverse labels, hierarchy, and term metadata in JSONB where needed [@models]. This schema layer is the database contract behind the dynamic metadata concept.

`MetadataMapping` links a field definition to export targets by `format_key` and `target_path`, with a uniqueness constraint across field, format, and target path [@models]. That means export mapping is stored beside schema configuration instead of being encoded directly into individual record rows.

## Relations, Media, And Configuration

Relations are generic rows with `from_type`, `from_id`, `to_type`, `to_id`, `relation_type`, JSONB metadata, and indexes for both directions [@models]. Media files belong to objects through a foreign key and store filename, MIME type, filesystem path, IIIF manifest JSON, status, primary-image flag, and rights fields [@models].

`MediaImportReference` stores a pending link from an object to a source filename before the file itself is uploaded. It keeps the original filename and a normalized basename used for matching. The table has indexes on `object_id` and `normalized_filename`, a uniqueness constraint across both columns, and an object foreign key with cascade deletion [@models] [@media-reference-migration]. These technical references remain outside the object's configurable `metadata` JSONB. A successful batch upload consumes its matching reference; a failed upload leaves it available for retry.

Several product settings are singleton-like records. `PortalConfig` and `AdminConfig` use a string primary key defaulting to `default`, and both store structured settings in ordinary columns and JSONB fields [@models]. `AppSecret` stores encrypted values by key, while `AuthoritySource` stores adapter class names and adapter config in JSONB [@models].

## Audit, Snapshots, And Versions

`AuditLog` records record type, record id, optional user id, action, changed fields as JSONB, and creation time, with indexes for record lookup and time-based access [@models]. `RecordSnapshot` stores labeled JSONB snapshots for a record with optional creator and timestamp [@models].

Primary records also carry an integer `version` column. Migration `0027_record_version.py` adds that column with server default `1` to objects, entities, places, occurrences, and procedures [@version-migration]. That makes optimistic-locking state part of the same primary record shell as status and timestamps.

## Related Pages

The persistence model underpins the [Schema Engine](../../concepts/metadata/schema-engine) and [Primary Record Types](../../concepts/domain/primary-record-types) concepts. It also connects to [Audit And Snapshots](../workflows/audit-and-snapshots) because audit rows, snapshot rows, and version columns are stored in the same database model. The table split is recorded as [Separate Record Tables](../../decisions/data/separate-record-tables).
