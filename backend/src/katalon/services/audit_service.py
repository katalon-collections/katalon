import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import AuditLog

_MAX_DIFF_VALUE_LEN = 200


def _display_value(value: object) -> object:
    """Render a metadata value for the audit-log diff.

    The admin UI renders diff values with ``String()``, which turns a raw
    dict/list into the literal text "[object Object]" — stringify
    non-primitives ourselves (truncated) instead.
    """
    if value is None or isinstance(value, str | int | float | bool):
        return value
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    if len(text) > _MAX_DIFF_VALUE_LEN:
        text = text[:_MAX_DIFF_VALUE_LEN] + "…"
    return text


def diff_fields(old: dict, new: dict) -> dict | None:
    """Reduce old/new field dicts to only the fields that actually changed.

    ``metadata`` is expanded so each changed metadata field shows up as its
    own ``metadata.<name>`` entry with its actual old/new value, instead of
    collapsing the whole metadata blob into one opaque "changed" marker.
    Returns None if nothing changed.
    """
    changed_old: dict = {}
    changed_new: dict = {}
    for key, new_value in new.items():
        old_value = old.get(key)
        if old_value == new_value:
            continue
        if key == "metadata" and (isinstance(old_value, dict) or isinstance(new_value, dict)):
            old_meta = old_value or {}
            new_meta = new_value or {}
            for mkey in sorted(set(old_meta) | set(new_meta)):
                mold, mnew = old_meta.get(mkey), new_meta.get(mkey)
                if mold == mnew:
                    continue
                changed_old[f"metadata.{mkey}"] = _display_value(mold)
                changed_new[f"metadata.{mkey}"] = _display_value(mnew)
            continue
        changed_old[key] = _display_value(old_value)
        changed_new[key] = _display_value(new_value)
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
