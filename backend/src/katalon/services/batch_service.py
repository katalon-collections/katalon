# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Any
from typing import cast as type_cast

from sqlalchemy import Text, cast, select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.exc import StaleDataError

from katalon.core.models import (
    Entity,
    FieldDefinition,
    Object,
    Occurrence,
    Place,
    Procedure,
    Relation,
)
from katalon.services.audit_service import diff_fields, log_change
from katalon.services.pid_service import ensure_pids_on_publish
from katalon.services.relation_service import sync_schema_relations
from katalon.services.schema_service import prepare_metadata, validate_metadata
from katalon.services.search_service import index_record

logger = logging.getLogger(__name__)

_MODEL_MAP: dict[str, type[Object] | type[Entity] | type[Place] | type[Occurrence] | type[Procedure]] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "procedure": Procedure,
}

_SUBTYPE_KEY: dict[str, str] = {
    "object": "object_type",
    "entity": "entity_type",
    "place": "place_type",
    "occurrence": "occurrence_type",
    "procedure": "procedure_type",
}

_STATUS_VALUES: dict[str, set[str]] = {
    "object": {"draft", "internal", "public"},
    "entity": {"draft", "internal", "public"},
    "place": {"draft", "internal", "public"},
    "occurrence": {"draft", "internal", "public"},
    "procedure": {"draft", "active", "completed", "cancelled"},
}

_LOGGABLE_RECORD_TYPES = {"object", "entity", "place", "occurrence", "procedure"}


def get_model(record_type: str) -> type[Object] | type[Entity] | type[Place] | type[Occurrence] | type[Procedure]:
    model = _MODEL_MAP.get(record_type)
    if model is None:
        raise ValueError(f"Unbekannter Record-Typ: {record_type}")
    return model


def _not_deleted_clause(model: Any) -> Any:
    if hasattr(model, "deleted_at"):
        return model.deleted_at.is_(None)
    return True


def _get_subtype_value(record: Any, record_type: str) -> str | None:
    key = _SUBTYPE_KEY.get(record_type)
    if not key:
        return None
    return getattr(record, key, None)


async def resolve_record_ids(
    db: Any,
    record_type: str,
    *,
    ids: Sequence[uuid.UUID] | None = None,
    filters: dict[str, Any] | None = None,
) -> list[uuid.UUID]:
    """Resolve the set of record IDs a batch operation should target.

    Supports an explicit list of IDs or the same filters used by the list
    endpoints so the frontend can target "all records matching the current
    search/filter".
    """
    model: Any = get_model(record_type)

    if ids is not None:
        stmt = select(model.id).where(model.id.in_(list(ids)), _not_deleted_clause(model))
        result = await db.execute(stmt)
        found = {row[0] for row in result.all()}
        # Preserve input order and filter out missing/deleted IDs.
        return [id_ for id_ in ids if id_ in found]

    filters = filters or {}
    stmt = select(model.id).where(_not_deleted_clause(model))

    status = filters.get("status")
    if status:
        stmt = stmt.where(model.status == status)

    subtype_key = _SUBTYPE_KEY.get(record_type)
    subtype = filters.get(subtype_key) if subtype_key else None
    if subtype:
        stmt = stmt.where(getattr(model, _SUBTYPE_KEY[record_type]) == subtype)

    q = filters.get("q")
    if q:
        stmt = stmt.where(
            model.idno.icontains(q, autoescape=True)
            | cast(model.metadata_, Text).icontains(q, autoescape=True)
        )

    if record_type == "procedure":
        due_before = filters.get("due_before")
        if due_before:
            stmt = stmt.where(model.due_date <= due_before)
        reference_number = filters.get("reference_number")
        if reference_number:
            stmt = stmt.where(model.reference_number.icontains(reference_number, autoescape=True))

    result = await db.execute(stmt.order_by(model.updated_at.desc()))
    return [row[0] for row in result.all()]


async def _load_field_definition(
    db: Any, record_type: str, field_name: str, subtype: str | None
) -> FieldDefinition | None:
    from sqlalchemy import or_

    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == record_type,
            FieldDefinition.name == field_name,
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.parent_id.is_(None),
            or_(FieldDefinition.target_subtype.is_(None), FieldDefinition.target_subtype == subtype),
        )
    )
    return type_cast(FieldDefinition | None, result.scalar_one_or_none())


def _empty_value_for_field(field: FieldDefinition) -> Any:
    if field.is_repeatable:
        return []
    if field.field_type == "boolean":
        return False
    if field.field_type in ("number",):
        return None
    return ""


async def _apply_status_change(
    db: Any,
    record: Any,
    record_type: str,
    value: str,
    user_id: uuid.UUID | None,
    batch_job_id: uuid.UUID,
) -> bool:
    allowed = _STATUS_VALUES.get(record_type, set())
    if value not in allowed:
        raise ValueError(f"Ungültiger Status '{value}' für {record_type}.")

    old_fields = {"status": record.status, "metadata": record.metadata_}
    record.status = value

    if value == "public" and old_fields["status"] not in ("public", "published"):
        # Batch publishing also auto-mints missing PIDs; a mint failure rolls
        # back this record's nested transaction and lands in the batch errors.
        await ensure_pids_on_publish(db, record_type, record, user_id)

    diff = diff_fields(old_fields, {"status": record.status, "metadata": record.metadata_})
    if diff:
        diff["batch_job_id"] = str(batch_job_id)
        await log_change(
            db,
            record_type=record_type,
            record_id=record.id,
            user_id=user_id,
            action="batch_update",
            changed_fields=diff,
        )
    return True


async def _apply_field_operation(
    db: Any,
    record: Any,
    record_type: str,
    operation_type: str,
    field_name: str,
    value: Any,
    user_id: uuid.UUID | None,
    batch_job_id: uuid.UUID,
    can_edit_locked: bool = False,
) -> bool:
    subtype = _get_subtype_value(record, record_type)
    field = await _load_field_definition(db, record_type, field_name, subtype)
    if field is None:
        field = await _load_field_definition(db, record_type, field_name, None)
    if field is None:
        raise ValueError(f"Feld '{field_name}' nicht im Schema für {record_type}.")
    if field.field_type == "group":
        raise ValueError(f"Gruppenfelder können nicht per Batch bearbeitet werden: '{field_name}'.")

    old_metadata = record.metadata_.copy()

    metadata = await prepare_metadata(
        db,
        record_type,
        record.metadata_,
        subtype,
        existing=record.metadata_,
        can_edit_locked=can_edit_locked,
    )

    if operation_type == "set_field":
        metadata[field_name] = value
    elif operation_type == "append_field":
        if not field.is_repeatable:
            raise ValueError(f"Feld '{field_name}' ist nicht wiederholbar; Anfügen nicht möglich.")
        existing = metadata.get(field_name)
        if not isinstance(existing, list):
            existing = []
        existing.append(value)
        metadata[field_name] = existing
    elif operation_type == "clear_field":
        metadata[field_name] = _empty_value_for_field(field)
    else:
        raise ValueError(f"Unbekannte Feld-Operation: {operation_type}")

    errors = await validate_metadata(db, record_type, metadata, subtype, skip_required=True)
    if errors:
        raise ValueError("; ".join(errors))

    record.metadata_ = metadata
    flag_modified(record, "metadata_")

    await sync_schema_relations(db, record_type, record.id, metadata)

    diff = diff_fields({"status": record.status, "metadata": old_metadata}, {"status": record.status, "metadata": metadata})
    if diff:
        diff["batch_job_id"] = str(batch_job_id)
        await log_change(
            db,
            record_type=record_type,
            record_id=record.id,
            user_id=user_id,
            action="batch_update",
            changed_fields=diff,
        )
    return True


async def _log_relation_change(
    db: Any,
    rel: Relation,
    user_id: uuid.UUID | None,
    action: str,
    batch_job_id: uuid.UUID,
) -> None:
    changed = {
        "relation_id": str(rel.id),
        "relation_type": rel.relation_type,
        "batch_job_id": str(batch_job_id),
    }
    for record_type, record_id, other_type, other_id in (
        (rel.from_type, rel.from_id, rel.to_type, rel.to_id),
        (rel.to_type, rel.to_id, rel.from_type, rel.from_id),
    ):
        if record_type not in _LOGGABLE_RECORD_TYPES:
            continue
        await log_change(
            db,
            record_type=record_type,
            record_id=record_id,
            user_id=user_id,
            action=action,
            changed_fields={
                **changed,
                "related_record_type": other_type,
                "related_record_id": str(other_id),
            },
        )


async def _apply_relation_operation(
    db: Any,
    record: Any,
    record_type: str,
    operation_type: str,
    to_type: str,
    to_id: uuid.UUID,
    relation_type: str,
    user_id: uuid.UUID | None,
    batch_job_id: uuid.UUID,
) -> bool:
    from katalon.services.relation_type_service import validate_relation_type_applicability

    applicability_error = await validate_relation_type_applicability(db, record_type, to_type, relation_type)
    if applicability_error:
        raise ValueError(applicability_error)

    if operation_type == "add_relation":
        existing = await db.execute(
            select(Relation).where(
                Relation.from_type == record_type,
                Relation.from_id == record.id,
                Relation.to_type == to_type,
                Relation.to_id == to_id,
                Relation.relation_type == relation_type,
            )
        )
        if existing.scalar_one_or_none():
            return False
        rel = Relation(
            from_type=record_type,
            from_id=record.id,
            to_type=to_type,
            to_id=to_id,
            relation_type=relation_type,
            metadata_={},
        )
        db.add(rel)
        await db.flush()
        await _log_relation_change(db, rel, user_id, "relation_add", batch_job_id)
        return True

    if operation_type == "remove_relation":
        result = await db.execute(
            select(Relation).where(
                Relation.from_type == record_type,
                Relation.from_id == record.id,
                Relation.to_type == to_type,
                Relation.to_id == to_id,
                Relation.relation_type == relation_type,
            )
        )
        rel = result.scalar_one_or_none()
        if rel is None:
            return False
        await _log_relation_change(db, rel, user_id, "relation_delete", batch_job_id)
        await db.delete(rel)
        return True

    raise ValueError(f"Unbekannte Relations-Operation: {operation_type}")


async def apply_batch(
    db: Any,
    record_type: str,
    record_ids: Sequence[uuid.UUID],
    operation: Any,
    user_id: uuid.UUID | None,
    batch_job_id: uuid.UUID,
    *,
    can_edit_locked: bool = False,
) -> dict[str, Any]:
    """Apply a batch operation to a list of records.

    Each record is processed in its own nested transaction so validation or
    version conflicts do not roll back sibling updates.
    """
    model = get_model(record_type)
    affected = 0
    errors: list[str] = []

    for record_id in record_ids:
        try:
            async with db.begin_nested():
                # Refresh from DB inside the nested transaction to avoid stale rows.
                record = await db.get(model, record_id)
                if record is None or (hasattr(record, "deleted_at") and record.deleted_at is not None):
                    raise ValueError("Datensatz nicht gefunden.")

                op_type = operation.type
                changed = False

                if op_type == "set_status":
                    changed = await _apply_status_change(
                        db, record, record_type, operation.value, user_id, batch_job_id
                    )
                elif op_type in ("set_field", "append_field", "clear_field"):
                    changed = await _apply_field_operation(
                        db,
                        record,
                        record_type,
                        op_type,
                        operation.field,
                        getattr(operation, "value", None),
                        user_id,
                        batch_job_id,
                        can_edit_locked=can_edit_locked,
                    )
                elif op_type in ("add_relation", "remove_relation"):
                    changed = await _apply_relation_operation(
                        db,
                        record,
                        record_type,
                        op_type,
                        operation.relation_to_type,
                        operation.relation_to_id,
                        operation.relation_type,
                        user_id,
                        batch_job_id,
                    )
                else:
                    raise ValueError(f"Unbekannte Operation: {op_type}")

                if changed:
                    await db.flush()
                    await index_record(record_type, record, db)
                    affected += 1

        except StaleDataError:
            errors.append(f"{record_id}: Datensatz wurde zwischenzeitlich geändert.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Batch operation failed for %s/%s: %s", record_type, record_id, exc, exc_info=True)
            errors.append(f"{record_id}: {exc}")

    return {"affected": affected, "errors": errors, "batch_job_id": batch_job_id}
