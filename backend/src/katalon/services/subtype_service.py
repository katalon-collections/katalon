# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import (
    Entity,
    FieldDefinition,
    FormVariant,
    FormVariantRoleDefault,
    Object,
    Occurrence,
    Place,
    Procedure,
    RecordSubtype,
)

PRIMARY_TYPES = {"object", "entity", "place", "occurrence", "procedure"}
_TYPE_MODEL_FIELD = {
    "object": (Object, "object_type"),
    "entity": (Entity, "entity_type"),
    "place": (Place, "place_type"),
    "occurrence": (Occurrence, "occurrence_type"),
    "procedure": (Procedure, "procedure_type"),
}


def validate_primary_type(primary_type: str) -> None:
    if primary_type not in PRIMARY_TYPES:
        raise HTTPException(status_code=422, detail="Ungültiger Primärtyp.")


def normalize_subtype_name(raw_value: str | None, *, allow_null: bool) -> str | None:
    if raw_value is None:
        if allow_null:
            return None
        raise HTTPException(status_code=422, detail="Subtyp ist erforderlich.")
    value = raw_value.strip()
    if not value:
        if allow_null:
            return None
        raise HTTPException(status_code=422, detail="Subtyp ist erforderlich.")
    return value


async def ensure_subtype_exists(
    db: AsyncSession, primary_type: str, subtype_name: str | None
) -> None:
    validate_primary_type(primary_type)
    if subtype_name is None:
        return
    result = await db.execute(
        select(RecordSubtype).where(
            RecordSubtype.primary_type == primary_type,
            RecordSubtype.name == subtype_name,
        )
    )
    subtype = result.scalar_one_or_none()
    if subtype is None:
        raise HTTPException(status_code=422, detail=f"Ungültiger Subtyp '{subtype_name}' für {primary_type}.")


async def subtype_has_assigned_records(
    db: AsyncSession, primary_type: str, subtype_name: str
) -> bool:
    validate_primary_type(primary_type)
    model, field_name = _TYPE_MODEL_FIELD[primary_type]
    field = getattr(model, field_name)
    count = (
        await db.execute(select(func.count()).select_from(model).where(field == subtype_name))
    ).scalar_one()
    return count > 0


async def retire_subtype_configuration(
    db: AsyncSession, primary_type: str, subtype_name: str
) -> None:
    """Retire configuration scoped to a deleted subtype without touching records."""
    validate_primary_type(primary_type)
    await db.execute(
        update(FieldDefinition)
        .where(
            FieldDefinition.target_type == primary_type,
            FieldDefinition.target_subtype == subtype_name,
        )
        .values(is_deleted=True)
    )
    variants = list(
        (
            await db.execute(
                select(FormVariant.id).where(
                    FormVariant.target_type == primary_type,
                    FormVariant.target_subtype == subtype_name,
                )
            )
        ).scalars()
    )
    if variants:
        await db.execute(
            update(FormVariant)
            .where(FormVariant.id.in_(variants))
            .values(is_deleted=True)
        )
        await db.execute(
            delete(FormVariantRoleDefault).where(FormVariantRoleDefault.variant_id.in_(variants))
        )


async def has_any_subtypes(db: AsyncSession, primary_type: str) -> bool:
    """Return True if at least one subtype is configured for this primary type."""
    validate_primary_type(primary_type)
    count = (
        await db.execute(
            select(func.count())
            .select_from(RecordSubtype)
            .where(RecordSubtype.primary_type == primary_type)
        )
    ).scalar_one()
    return count > 0
