---
title: "Installation Profiles"
summary: "Installation profiles are a proposed bundle of field definitions, subtypes, and vocabulary imports for a GLAM domain, applied through the existing admin schema configuration surface rather than fixed at install time."
topics: [concepts, domain, metadata, schema, onboarding, standards]
sources:
  - id: issue
    type: web
    url: https://github.com/karkraeg/Katalon/issues/361
  - id: onboarding-issue
    type: web
    url: https://github.com/karkraeg/Katalon/issues/188
  - id: record-subtypes
    type: file
    path: almanac/concepts/metadata/record-subtypes.md
  - id: vocabularies
    type: file
    path: almanac/concepts/metadata/vocabularies.md
  - id: storage-locations
    type: file
    path: almanac/decisions/data/storage-locations.md
  - id: primary-record-types
    type: file
    path: almanac/concepts/domain/primary-record-types.md
  - id: procedures
    type: file
    path: almanac/concepts/domain/procedures.md
---

**Status: proposed, not implemented.** This page documents a design tracked in issue #361; no backend or frontend code exists for it yet [@issue]. It is written now because the design leans entirely on existing mechanisms (schema engine, subtypes, vocabulary import, Collection hierarchy, StorageLocation), and a later implementation should not have to re-derive that mapping.

An installation profile is a curated bundle of `RecordSubtype` rows, `FieldDefinition` rows, and vocabulary/term sets for one recognizable GLAM domain (library, museum, archive), applied as a unit so an institution gets a standards-aligned starting schema instead of building one field by field.

## Relationship To AI Onboarding (#188)

Issue #188 asked the same underlying question — how does a new installation get from an empty schema to a usable one — and answered it with an AI chat that helps draft input forms interactively [@onboarding-issue]. Profiles are a complementary, deterministic path for the common case: an institution that already knows it catalogs library holdings or museum objects does not need an AI conversation to arrive at a schema that follows RDA, LIDO, or ISAD(G) — it needs the standard schema applied directly, then refined per field with the existing AI tooling if needed. Both mechanisms can coexist; a profile does not replace the chat-based onboarding, it gives it a starting point for the domains where one is obvious.

## Why An Admin Import, Not An Install-Time Choice

Katalon's schema configuration already lives entirely in the database rather than in config files: `FieldDefinition.target_type` plus optional `target_subtype` scope fields to a primary type or one configured subtype, and no subtype is seeded automatically except Procedure's six defaults [@record-subtypes]. Vocabularies already have an import pipeline, including selective SKOS subtree extraction from external thesauri such as Getty AAT by `top_concept` URI [@vocabularies].

A profile is naturally another entry point into that same configuration surface — an admin-triggered import, not a decision fixed during `katalon-cli` install or a one-time first-start wizard step. That makes profiles appliable at any time, repeatably, and in combination (for example a library profile plus an institution's own archive holdings in the same installation). A first-start wizard could later offer a profile as a shortcut, but it would call the same import mechanism rather than owning separate logic.

## What A Profile Bundles

- `RecordSubtype` rows scoping fields to a domain-specific subtype, e.g. `occurrence_type = bibliographic_record` or `collection_type = bestand` [@record-subtypes]
- `FieldDefinition` rows per `(target_type, target_subtype)` [@record-subtypes]
- Vocabulary and term sets, either shipped inline (small controlled lists like an ISAD(G) level-of-description vocabulary) or pulled through the existing SKOS import for large external authorities like Getty AAT or GND-adjacent thesauri [@vocabularies]
- Optionally, relation-type vocabulary terms constrained with `applies_from`/`applies_to`, the same mechanism already used for `normal_location`/`current_location` between Object and StorageLocation [@storage-locations]

No new primary record type or table is needed. Profiles map onto Katalon's seven existing primary types — Object, Entity, Place, Occurrence, Procedure, Collection, and StorageLocation [@primary-record-types] [@storage-locations].

## Three Proposed Profiles

### Library (RDA / FRBR-LRM, simplified to two levels)

Full FRBR Work/Expression/Manifestation/Item is flattened to two records, matching how most integrated library systems already simplify it:

- **Occurrence**, subtype `bibliographic_record` (combines Work, Expression, and Manifestation): title (repeatable, with language), parallel title, statement of responsibility, author/editor (relation to Entity, with role), publisher, place of publication (relation to Place), year, edition, extent, language (vocab, ISO 639), ISBN/ISSN (repeatable), subject (vocab, GND subject terms), DDC/RVK classification (vocab), URL/URN/DOI
- **Object**, subtype `item`: shelf mark, barcode, item status (vocab: available/on loan/missing/withdrawn), provenance, condition; relation "is item of" → the bibliographic Occurrence; `normal_location`/`current_location` → StorageLocation for shelf/room placement
- **Entity**: person/corporate body for author, editor, publisher — connects to the existing GND authority adapter
- **Place**: place of publication (geographic)
- **StorageLocation**: building/room/shelf hierarchy for item placement

### Museum (LIDO / CIDOC-CRM / SPECTRUM)

- **Object**: object name (vocab, Getty AAT), inventory number, material/technique (vocab, AAT, repeatable), dimensions (structured: height/width/depth/weight plus unit), dating (from/to, imprecise allowed), maker/artist (relation to Entity, role "creator"), condition (vocab), description (multilingual), rights/license (vocab); `member_of` → Collection for a named collection group; `normal_location`/`current_location` → StorageLocation
- **Procedure**: no new subtypes needed. The seeded defaults `acquisition`, `loan_out`, `loan_in`, and `conservation` already match SPECTRUM's core procedure units [@procedures]; the profile only adds `target_subtype`-scoped fields per unit (e.g. acquisition method and price on `acquisition`; insurance value and condition report on `loan_out`/`loan_in`; conservator and treatment on `conservation`)
- **Entity**: artist/maker, former owner, lender/borrower, conservator
- **Place**: place of origin (geographic)
- **Collection**: named collection group, hierarchical

### Archive (ISAD(G) / ISAAR-CPF)

- **Collection**, using its native `parent_id` hierarchy for fonds → series → file rather than generic relations [@primary-record-types]: reference code, title, date range, extent, creating body/provenance (relation to Entity), scope and content note, appraisal/retention, access conditions and closure period, use restrictions
- **Object**, subtype `document`: the lowest description level (single item/digitized document); `member_of` → the containing Collection (file)
- **Entity**: creating body per ISAAR(CPF) — name, dates of existence, administrative/biographical history
- **Place**: place of creation (geographic)
- **StorageLocation**: repository/shelf/box for physical holdings

## Open Design Questions

- Conflict handling when a field name or vocabulary term code from a profile already exists (skip, merge, or reject the whole import)
- Whether profiles should be combinable on top of each other, or only ever a clean-slate starting point
- How much DDC/RVK/ISAD(G) vocabulary ships as inline term data versus being documented only as an import template for institutions to run themselves
- Whether the first-start wizard from #188 should surface this mechanism once it exists, and how the two onboarding paths are presented together

## Related Pages

Profiles configure the same surface described in [Schema Engine](../metadata/schema-engine), [Record Subtypes](../metadata/record-subtypes), and [Vocabularies](../metadata/vocabularies), and place records into [Primary Record Types](primary-record-types) and [Procedures](procedures) rather than introducing new ones.
