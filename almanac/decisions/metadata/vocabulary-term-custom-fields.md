---
title: "Vocabulary Term Custom Fields"
summary: "Vocabulary terms use JSONB metadata and schema-engine field definitions instead of a separate vocabulary-only metadata system."
topics: [decisions, metadata, vocabularies, schema, authority]
sources:
  - id: decision
    type: file
    path: .agents/knowledge/decisions/vocabulary-custom-fields.md
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: migration
    type: file
    path: backend/migrations/versions/0025_vocab_term_metadata.py
  - id: data-doc
    type: file
    path: docs/01_datenmodell.md
---

Katalon gives vocabulary terms custom metadata without creating a second schema system. The current model stores term values in `VocabularyTerm.metadata_`, while `FieldDefinition.target_type` can address `vocabulary_term` for schema-managed term fields [@models]. The decision grew from a concrete import problem: vocabulary terms had no metadata storage path, so external IDs and authority enrichment needed a minimal but durable home [@decision].

## Context

Vocabularies are controlled lists for cataloguing fields and relation types. The data model defines `vocabularies` with a name and hierarchy flag, and `vocabulary_terms` with a term key, multilingual label, metadata JSONB, and optional parent term [@data-doc]. That term-level metadata matters because vocabulary entries can carry authority references such as GND or Wikidata IDs [@data-doc].

The local decision record says `VocabularyTerm` originally lacked a `metadata_` column and configurable extra fields, unlike Object, Entity, Place, and Occurrence [@decision]. The immediate bug was that imported `external_id` data could disappear because no storage path existed for it [@decision].

## Decision

The first implementation step added a JSONB `metadata` column to `vocabulary_terms`. Migration `0025` adds that non-null column with a server default of `{}` and drops it on downgrade [@migration]. The current ORM maps the column as `VocabularyTerm.metadata_` and comments that it stores values for vocabulary-term field definitions [@models].

The decision then converged on the existing schema engine rather than a vocabulary-only field system. `FieldDefinition.target_type` is a string-based target column, and the current model uses the same field-definition structure for normal records and vocabulary terms [@models]. The decision record states the final target as `vocabulary_term`, with each vocabulary acting as the subtype and values stored in `VocabularyTerm.metadata_` [@decision].

Authority data is part of the reason for the design. The decision chose structured authority metadata of `{source, external_id, label}` so term metadata could reuse the existing authority-source model instead of storing opaque strings [@decision]. The data model documentation shows term metadata containing an `authorities` list with the same source, external ID, and label shape [@data-doc].

## Consequences

Vocabulary metadata follows the same mental model as record metadata: field definitions describe allowed fields, and JSONB stores values. That keeps [Vocabularies](../../concepts/metadata/vocabularies) connected to the [Schema Engine](../../concepts/metadata/schema-engine) instead of creating a parallel configuration surface.

The design is intentionally bounded. The decision record says vocabulary-term field types were limited to text, number, boolean, and authority to avoid pulling full record-form behavior into term editing [@decision]. That limit is part of the decision, not an accidental omission.

Future vocabulary work should extend the shared schema path when possible. Adding hard-coded term columns for each new enrichment field would undo the purpose of `VocabularyTerm.metadata_`, while building a separate field-definition table for terms would duplicate the schema engine this decision deliberately reused.
