import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import AuditLog


def diff_fields(old: dict, new: dict) -> dict | None:
    """Reduce old/new field dicts to only the fields that actually changed.

    Dict/list values (e.g. ``metadata``) are summarized as "geändert" rather
    than embedded raw — the admin UI renders diff values with ``String()``,
    which turns a raw object into the literal text "[object Object]".
    Returns None if nothing changed.
    """
    changed_old: dict = {}
    changed_new: dict = {}
    for key, new_value in new.items():
        old_value = old.get(key)
        if old_value == new_value:
            continue
        if isinstance(old_value, dict | list) or isinstance(new_value, dict | list):
            changed_old[key] = "geändert" if old_value else "—"
            changed_new[key] = "geändert" if new_value else "—"
        else:
            changed_old[key] = old_value
            changed_new[key] = new_value
    if not changed_old:
        return None
    return {"old": changed_old, "new": changed_new}


async def log_change(
    db: AsyncSession,
    *,
    record_type: str,
    record_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    changed_fields: dict | None = None,
) -> None:
    entry = AuditLog(
        record_type=record_type,
        record_id=record_id,
        user_id=user_id,
        action=action,
        changed_fields=changed_fields or {},
    )
    db.add(entry)
    # session commit happens in get_db()
