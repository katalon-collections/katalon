import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import AuditLog

_MAX_DIFF_VALUE_LEN = 200

# Mirrors TITLE_FIELD_NAMES in frontend/admin/src/components/screens/ScreenForm.tsx —
# keep both lists in sync.
TITLE_FIELD_NAMES = ["label", "title", "titel", "name", "display_name", "place_name", "bezeichnung"]


def extract_title(md: dict[str, Any] | None) -> str | None:
    if not md:
        return None
    for key in TITLE_FIELD_NAMES:
        val = md.get(key)
        if not val:
            continue
        if isinstance(val, str):
            return val
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("value") or first.get("label") or None
    return None


def format_label(title: str | None, idno: str | None, fallback: str) -> str:
    if not title:
        return idno or fallback
    return f"{title} ({idno})" if idno else title


def delete_label_fields(idno: str | None, metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Snapshot idno/title into the delete audit entry's changed_fields.

    The record row is gone by the time the audit log is displayed, so the
    label shown there must survive the deletion instead of being resolved
    from a live lookup.
    """
    fields: dict[str, Any] = {}
    if idno:
        fields["idno"] = idno
    title = extract_title(metadata)
    if title:
        fields["title"] = title
    return fields


def collapse_value(value: object) -> object | None:
    """Collapse vocab-ish values to their human-readable label.

    Vocab/title fields store objects like ``{"id": <uuid>, "label": "..."}``
    (or ``[{"value": "...", "lang": "..."}]`` for repeatable/i18n fields), so
    a raw JSON diff leaks the internal DB id. Pre-serialized JSON strings are
    parsed first so legacy audit entries (whose values were stringified at log
    time) are handled too. When every item of a value can be reduced to a
    label, return it; otherwise return None so the caller falls back to the
    original rendering.
    """

    def label_of(item: object) -> str | None:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            for key in ("label", "value", "name"):
                v = item.get(key)
                if isinstance(v, str) and v:
                    return v
        return None

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or not (stripped.startswith("{") or stripped.startswith("[")):
            return None
        try:
            parsed = json.loads(value)
        except ValueError:
            return None
        return collapse_value(parsed)

    if isinstance(value, dict):
        return label_of(value)
    if isinstance(value, list):
        parts = [label_of(item) for item in value]
        labels = [part for part in parts if part is not None]
        if labels and len(labels) == len(parts):
            return ", ".join(labels)
    return None


def _display_value(value: object) -> object:
    """Render a metadata value for the audit-log diff.

    The admin UI renders diff values with ``String()``, which turns a raw
    dict/list into the literal text "[object Object]" — stringify
    non-primitives ourselves (truncated) instead.
    """
    if value is None or isinstance(value, int | float | bool):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            return value
    short = collapse_value(value)
    if short is not None:
        return short
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    if len(text) > _MAX_DIFF_VALUE_LEN:
        text = text[:_MAX_DIFF_VALUE_LEN] + "…"
    return text


def diff_fields(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any] | None:
    """Reduce old/new field dicts to only the fields that actually changed.

    ``metadata`` is expanded so each changed metadata field shows up as its
    own ``metadata.<name>`` entry with its actual old/new value, instead of
    collapsing the whole metadata blob into one opaque "changed" marker.
    Returns None if nothing changed.
    """
    changed_old: dict[str, Any] = {}
    changed_new: dict[str, Any] = {}
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
    changed_fields: dict[str, Any] | None = None,
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
