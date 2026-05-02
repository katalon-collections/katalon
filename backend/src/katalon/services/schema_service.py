import functools

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition


async def get_field_definitions(db: AsyncSession, target_type: str) -> list[FieldDefinition]:
    result = await db.execute(
        select(FieldDefinition)
        .where(FieldDefinition.target_type == target_type, FieldDefinition.is_deleted.is_(False))
        .order_by(FieldDefinition.sort_order)
    )
    return list(result.scalars().all())


async def validate_metadata(
    db: AsyncSession, record_type: str, metadata: dict
) -> list[str]:
    """Return list of validation error messages (empty = valid)."""
    fields = await get_field_definitions(db, record_type)
    errors: list[str] = []

    for field in fields:
        value = metadata.get(field.name)

        if field.is_required and (value is None or value == "" or value == []):
            errors.append(f"Feld '{field.name}' ist erforderlich.")
            continue

        if value is None:
            continue

        if field.is_repeatable:
            if not isinstance(value, list):
                errors.append(f"Feld '{field.name}' muss eine Liste sein (wiederholbar).")
        else:
            if isinstance(value, list):
                errors.append(f"Feld '{field.name}' darf keine Liste sein (nicht wiederholbar).")

    return errors
