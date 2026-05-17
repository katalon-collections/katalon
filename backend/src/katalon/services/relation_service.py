from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition, Relation


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


async def sync_schema_relations(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID,
    metadata_: dict,
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
            FieldDefinition.is_deleted.is_(False),
        )
    )
    rel_fields = result.scalars().all()
    if not rel_fields:
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

    # 3. Create new derived relations from metadata_
    for field in rel_fields:
        raw = metadata_.get(field.name)
        if not raw:
            continue

        entries: list[dict]
        if field.is_repeatable and isinstance(raw, list):
            entries = [e for e in raw if isinstance(e, dict) and e.get("id")]
        elif isinstance(raw, dict) and raw.get("id"):
            entries = [raw]
        else:
            continue

        target_type = (field.settings or {}).get("target_type", "")
        for entry in entries:
            db.add(
                Relation(
                    from_type=record_type,
                    from_id=record_id,
                    to_type=target_type,
                    to_id=uuid.UUID(str(entry["id"])),
                    relation_type=str(entry.get("relation_type", "")),
                    metadata_={"source_field": field.name, "is_schema_relation": True},
                    is_schema_derived=True,
                )
            )
