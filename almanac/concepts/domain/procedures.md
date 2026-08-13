---
title: "Procedures"
summary: "Procedures are Katalon's process records for object-related loans, acquisition, conservation, and other collection workflows."
topics: [concepts, domain, records, workflows, relations]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: procedures-api
    type: file
    path: backend/src/katalon/api/v1/procedures.py
  - id: relation-service
    type: file
    path: backend/src/katalon/services/relation_service.py
  - id: procedure-concept
    type: file
    path: docs/konzept-vorgaenge.md
---

Procedures are Katalon's records for time-bounded collection processes, not another kind of inventory entity. They cover outgoing and incoming loans, acquisition, conservation, object entry, deaccession, and configured local workflow types, with their own dates, reference number, status, dynamic metadata, audit log, search indexing, and relations to other records [@procedures-api]. Procedures connect to [Primary Record Types](primary-record-types) through [Generic Relations](../relations/generic-relations), and their backend behavior is part of [Record CRUD And Publishing](../../architecture/workflows/record-crud-and-publishing).

## What A Procedure Represents

The procedure concept document defines a Vorgang as a time-limited, state-changing process affecting one or more objects. It separates a loan contract, acquisition process, or conservation treatment from domain concepts such as an exhibition or work [@procedure-concept]. In code, the `Procedure` model has `procedure_type`, publication or workflow `status`, `start_date`, `end_date`, `due_date`, `reference_number`, JSONB `metadata`, `search_vector`, timestamps, and version [@models].

Procedure types are configured `RecordSubtype` rows under primary type `procedure`. Migration `0034_procedure_record_subtypes.py` creates the system types `loan_out`, `loan_in`, `acquisition`, `conservation`, `object_entry`, and `deaccession`; admins can create additional procedure subtypes. The API accepts only a configured subtype. Procedure statuses remain `draft`, `active`, `completed`, and `cancelled` [@procedures-api].

The six system types cannot be deleted, renamed, or moved to another primary type. This preserves the stable names used by procedure-specific business rules; additional procedure subtypes have no implicit workflow rule.

## Dynamic Metadata With Procedure Subtypes

Procedures use the same schema mechanism as other record families. The create and update endpoints call `prepare_metadata` and `validate_metadata` with target type `procedure` and the selected `procedure_type`, so configured fields can be validated for the process subtype [@procedures-api]. Draft Procedures can skip required metadata and missing ID number checks in the same broad pattern used for draft records [@procedures-api].

Schema relation fields are mirrored into the `relations` table after create and update. The procedure endpoints call `sync_schema_relations` with record type `procedure`, which makes relation fields in procedure metadata usable by generic relation queries [@procedures-api].

## Object Links And Loan Invariant

Procedures link to Objects through relation rows rather than through a dedicated join table. `procedure_object_ids` finds object IDs from either direction of a `procedure` to `object` relation, so the relation can be stored as Procedure to Object or Object to Procedure [@relation-service].

Outgoing loans have one hard invariant: an object cannot be part of two active `loan_out` Procedures at the same time. The procedure validator checks active outgoing loans for each linked object and returns a conflict when another active loan exists [@procedures-api]. The relation service implements that lookup by joining `Procedure` to `Relation` in both directions and filtering `Procedure.procedure_type == "loan_out"` and `Procedure.status == "active"` [@relation-service].

## Completion And Collection Status

Completing a Procedure sets its status to `completed`. If the request includes a valid collection status, the endpoint loads linked Objects, updates each object's `collection_status`, writes audit entries for those object changes, and reindexes each changed object [@procedures-api].

The API allows collection status values `active`, `pending`, `on_loan_in`, `on_loan_out`, `deaccessioned`, and `returned` during completion [@procedures-api]. The concept document states the product reason: process records can change object collection status, but automatic status transitions are avoided so staff keep control over the decision [@procedure-concept].

## Lifecycle Support

Procedure CRUD follows the same operational shape as other record APIs. Create and update write audit log entries and attempt Elasticsearch indexing; update uses `If-Match` optimistic locking through `check_version`; delete blocks when relations exist unless `force=true`, then removes relation rows before deleting the Procedure [@procedures-api].

Procedures support audit-log reads, but not snapshots. The procedure snapshot endpoints and form controls are absent; historical `record_snapshots` rows with `record_type = "procedure"` are retained rather than purged, but are inaccessible through the API and admin UI [@procedures-api].
