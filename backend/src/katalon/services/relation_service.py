# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import and_, func, or_, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import (
    Entity,
    FieldDefinition,
    Object,
    Occurrence,
    Place,
    Procedure,
    Relation,
)

_RECORD_MODELS: dict[str, Any] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "procedure": Procedure,
}


async def count_relations(db: AsyncSession, record_type: str, record_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            or_(
                and_(Relation.from_type == record_type, Relation.from_id == record_id),
                and_(Relation.to_type == record_type, Relation.to_id == record_id),
            )
        )
    )
    return result.scalar_one()


async def delete_relations(db: AsyncSession, record_type: str, record_id: uuid.UUID) -> None:
    await db.execute(
        sa_delete(Relation).where(
            or_(
                and_(Relation.from_type == record_type, Relation.from_id == record_id),
                and_(Relation.to_type == record_type, Relation.to_id == record_id),
            )
        )
    )


def procedure_object_pair(
    from_type: str,
    from_id: uuid.UUID,
    to_type: str,
    to_id: uuid.UUID,
) -> tuple[uuid.UUID, uuid.UUID] | None:
    if from_type == "procedure" and to_type == "object":
        return from_id, to_id
    if from_type == "object" and to_type == "procedure":
        return to_id, from_id
    return None


async def get_active_loan_out_for_object(
    db: AsyncSession,
    object_id: uuid.UUID,
    exclude_procedure_id: uuid.UUID | None = None,
) -> Procedure | None:
    stmt = (
        select(Procedure)
        .join(
            Relation,
            or_(
                and_(
                    Relation.from_type == "procedure",
                    Relation.from_id == Procedure.id,
                    Relation.to_type == "object",
                    Relation.to_id == object_id,
                ),
                and_(
                    Relation.to_type == "procedure",
                    Relation.to_id == Procedure.id,
                    Relation.from_type == "object",
                    Relation.from_id == object_id,
                ),
            ),
        )
        .where(Procedure.procedure_type == "loan_out", Procedure.status == "active")
        .limit(1)
    )
    if exclude_procedure_id:
        stmt = stmt.where(Procedure.id != exclude_procedure_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def lock_objects(db: AsyncSession, object_ids: list[uuid.UUID]) -> None:
    """Serialize loan checks for a deterministic set of object rows."""
    if object_ids:
        await db.execute(
            select(Object.id)
            .where(Object.id.in_(sorted(set(object_ids))))
            .order_by(Object.id)
            .with_for_update()
        )


async def procedure_object_ids(db: AsyncSession, procedure_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(Relation).where(
            or_(
                and_(
                    Relation.from_type == "procedure",
                    Relation.from_id == procedure_id,
                    Relation.to_type == "object",
                ),
                and_(
                    Relation.to_type == "procedure",
                    Relation.to_id == procedure_id,
                    Relation.from_type == "object",
                ),
            )
        )
    )
    ids: list[uuid.UUID] = []
    for rel in result.scalars().all():
        ids.append(rel.to_id if rel.from_type == "procedure" else rel.from_id)
    return ids


async def sync_schema_relations(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID,
    metadata_: dict[str, Any],
) -> None:
    """Mirror schema relation fields into the relations table.

    Deletes existing schema-derived relations for this record and recreates
    them based on current metadata_.  Idempotent — safe to call after every
    create/update.
    """
    # 1. Load field definitions for this type
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == record_type,
            FieldDefinition.field_type == "relation",
            FieldDefinition.parent_id.is_(None),
            FieldDefinition.is_deleted.is_(False),
        )
    )
    rel_fields = list(result.scalars().all())
    group_result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == record_type,
            FieldDefinition.field_type == "group",
            FieldDefinition.parent_id.is_(None),
            FieldDefinition.is_deleted.is_(False),
        )
    )
    group_fields = list(group_result.scalars().all())
    group_relation_fields: list[tuple[FieldDefinition, FieldDefinition]] = []
    for group in group_fields:
        children = await db.execute(
            select(FieldDefinition).where(
                FieldDefinition.parent_id == group.id,
                FieldDefinition.field_type == "relation",
                FieldDefinition.is_deleted.is_(False),
            )
        )
        group_relation_fields.extend((group, child) for child in children.scalars().all())
    if not rel_fields and not group_relation_fields:
        # Nothing to sync — just clean up any stale derived relations
        await db.execute(
            sa_delete(Relation).where(
                Relation.from_type == record_type,
                Relation.from_id == record_id,
                Relation.is_schema_derived.is_(True),
            )
        )
        return

    # 2. Delete existing derived relations for this record
    await db.execute(
        sa_delete(Relation).where(
            Relation.from_type == record_type,
            Relation.from_id == record_id,
            Relation.is_schema_derived.is_(True),
        )
    )

    # 3. Create new derived relations from metadata_, skipping any that would
    # duplicate a manually-created (non-schema) relation to the same target
    # with the same relation type.
    existing_manual = await db.execute(
        select(Relation.to_type, Relation.to_id, Relation.relation_type).where(
            Relation.from_type == record_type,
            Relation.from_id == record_id,
            Relation.is_schema_derived.is_(False),
        )
    )
    manual_keys = {(t, i, r) for t, i, r in existing_manual.all()}

    for field in rel_fields:
        raw = metadata_.get(field.name)
        if not raw:
            continue

        entries: list[dict[str, Any]]
        if field.is_repeatable and isinstance(raw, list):
            entries = [e for e in raw if isinstance(e, dict) and e.get("id")]
        elif isinstance(raw, dict) and raw.get("id"):
            entries = [raw]
        else:
            continue

        target_type = (field.settings or {}).get("target_type", "")
        for entry in entries:
            to_id = uuid.UUID(str(entry["id"]))
            relation_type = str(entry.get("relation_type", ""))
            if (target_type, to_id, relation_type) in manual_keys:
                continue
            db.add(
                Relation(
                    from_type=record_type,
                    from_id=record_id,
                    to_type=target_type,
                    to_id=to_id,
                    relation_type=relation_type,
                    metadata_={"source_field": field.name, "is_schema_relation": True},
                    is_schema_derived=True,
                )
            )
    for group, field in group_relation_fields:
        for instance in metadata_.get(group.name, []):
            if not isinstance(instance, dict):
                continue
            entry = cast(dict[str, Any], instance.get(field.name))
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            target_type = (field.settings or {}).get("target_type", "")
            to_id = uuid.UUID(str(entry["id"]))
            relation_type = str(entry.get("relation_type", ""))
            if (target_type, to_id, relation_type) in manual_keys:
                continue
            db.add(
                Relation(
                    from_type=record_type,
                    from_id=record_id,
                    to_type=target_type,
                    to_id=to_id,
                    relation_type=relation_type,
                    metadata_={
                        "source_field": f"{group.name}.{field.name}",
                        "is_schema_relation": True,
                    },
                    is_schema_derived=True,
                )
            )


async def resolve_relation_labels(
    db: AsyncSession,
    relations: list[Relation],
    *,
    public_only: bool = False,
) -> dict[tuple[str, uuid.UUID], str | None]:
    """Resolve a display label for every (type, id) endpoint referenced by relations.

    None means the record is missing (deleted) or, with public_only, no longer
    public — distinct from a resolvable record whose title happens to be empty
    (which still yields the idno fallback, or "" only if neither exists).
    """
    from katalon.services.public_metadata_service import filter_public_metadata, load_public_fields
    from katalon.services.search_service import _extract_title

    ids_by_type: dict[str, set[uuid.UUID]] = {}
    for rel in relations:
        ids_by_type.setdefault(rel.from_type, set()).add(rel.from_id)
        ids_by_type.setdefault(rel.to_type, set()).add(rel.to_id)

    labels: dict[tuple[str, uuid.UUID], str | None] = {}
    for record_type, ids in ids_by_type.items():
        model = _RECORD_MODELS.get(record_type)
        if model is None:
            for record_id in ids:
                labels[(record_type, record_id)] = None
            continue

        stmt = select(model).where(model.id.in_(ids))
        if hasattr(model, "deleted_at"):
            stmt = stmt.where(model.deleted_at.is_(None))
        if public_only:
            from katalon.core.visibility import PUBLIC_STATUSES
            stmt = stmt.where(model.status.in_(PUBLIC_STATUSES))
        records = {rec.id: rec for rec in (await db.execute(stmt)).scalars().all()}

        public_fields = await load_public_fields(db, record_type) if public_only else None
        for record_id in ids:
            rec = records.get(record_id)
            if rec is None:
                labels[(record_type, record_id)] = None
                continue
            md = rec.metadata_ or {}
            if public_only:
                subtype = getattr(rec, f"{record_type}_type", None)
                md = filter_public_metadata(md, public_fields or [], subtype)
            title = _extract_title(md) or (rec.idno or "")
            labels[(record_type, record_id)] = title or None
    return labels
