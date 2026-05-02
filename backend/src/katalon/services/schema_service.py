from __future__ import annotations

import re

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition


async def get_field_definitions(
    db: AsyncSession, target_type: str, target_subtype: str | None = None
) -> list[FieldDefinition]:
    q = select(FieldDefinition).where(
        FieldDefinition.target_type == target_type,
        FieldDefinition.is_deleted.is_(False),
    )
    if target_subtype:
        q = q.where(
            or_(FieldDefinition.target_subtype.is_(None), FieldDefinition.target_subtype == target_subtype)
        )
    result = await db.execute(q.order_by(FieldDefinition.sort_order))
    return list(result.scalars().all())


def _validate_pid_value(value: object, settings: dict, field_name: str) -> str | None:
    """Validate a single PID dict {"value": "...", "label": "..."}. Returns error or None."""
    if not isinstance(value, dict):
        return f"Feld '{field_name}': PID muss ein Objekt {{value, label}} sein."
    pid_val = value.get("value")
    if not pid_val or not isinstance(pid_val, str):
        return f"Feld '{field_name}': PID-Wert (value) darf nicht leer sein."
    pattern = settings.get("pattern")
    if pattern:
        try:
            if not re.fullmatch(pattern, pid_val):
                return f"Feld '{field_name}': '{pid_val}' entspricht nicht dem erwarteten Format."
        except re.error:
            pass
    return None


async def validate_metadata(
    db: AsyncSession, record_type: str, metadata: dict, target_subtype: str | None = None
) -> list[str]:
    """Return list of validation error messages (empty = valid)."""
    fields = await get_field_definitions(db, record_type, target_subtype)
    errors: list[str] = []

    for field in fields:
        value = metadata.get(field.name)

        if field.is_required and (value is None or value == "" or value == []):
            errors.append(f"Feld '{field.name}' ist erforderlich.")
            continue

        if value is None:
            continue

        if field.field_type == "pid":
            if field.is_repeatable:
                if not isinstance(value, list):
                    errors.append(f"Feld '{field.name}' muss eine Liste sein (wiederholbar).")
                else:
                    for item in value:
                        err = _validate_pid_value(item, field.settings, field.name)
                        if err:
                            errors.append(err)
            else:
                err = _validate_pid_value(value, field.settings, field.name)
                if err:
                    errors.append(err)
            continue

        if field.is_repeatable:
            if not isinstance(value, list):
                errors.append(f"Feld '{field.name}' muss eine Liste sein (wiederholbar).")
        else:
            if isinstance(value, list):
                errors.append(f"Feld '{field.name}' darf keine Liste sein (nicht wiederholbar).")

    return errors
