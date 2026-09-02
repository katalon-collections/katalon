# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import re
import uuid
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition


def _is_leap_year(year: int) -> bool:
    """Proleptic Gregorian leap rule; works for BCE years (astronomical numbering, year 0 = 1 v. Chr.)."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _is_valid_date_part(value: str) -> bool:
    """Accept ISO years, year-months, and real calendar dates (no qualifiers/range).

    BCE years use a leading minus with zero-padded year, e.g. "-0043" (44 v. Chr.;
    ISO 8601 year -0043 = 44 BCE due to the year-0 offset). Python's
    date.fromisoformat rejects negative years and year 0, so calendar checks run manually.
    """
    if re.fullmatch(r"-?\d{4}", value):
        return True
    month = re.fullmatch(r"(-?\d{4})-(\d{2})", value)
    if month:
        return 1 <= int(month.group(2)) <= 12
    full = re.fullmatch(r"(-?\d{4})-(\d{2})-(\d{2})", value)
    if not full:
        return False
    year = int(full.group(1))
    month_num = int(full.group(2))
    day = int(full.group(3))
    if not 1 <= month_num <= 12 or not 1 <= day <= 31:
        return False
    days_in_month = [31, 29 if _is_leap_year(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return day <= days_in_month[month_num - 1]


def _is_valid_qualified_date(value: str) -> bool:
    """Date part with optional EDTF-lite qualifier suffix: '~' (circa), '?' (unsicher), '~?' (beides)."""
    for suffix in ("~?", "~", "?"):
        if value.endswith(suffix):
            return _is_valid_date_part(value[: -len(suffix)])
    return _is_valid_date_part(value)


def _is_valid_date(value: object) -> bool:
    """Accept a single (optionally qualified) date, or a '/'-separated range with open ends.

    Examples: "1900", "1900~" (circa), "1900?" (unsicher), "1900/1950" (Zeitraum),
    "1900/" (nach 1900), "/1900" (vor 1900).
    """
    if not isinstance(value, str):
        return False
    if value.count("/") == 1:
        start, end = value.split("/")
        if not start and not end:
            return False
        return (start == "" or _is_valid_qualified_date(start)) and (
            end == "" or _is_valid_qualified_date(end)
        )
    return _is_valid_qualified_date(value)


async def get_field_definitions(
    db: AsyncSession, target_type: str, target_subtype: str | None = None
) -> list[FieldDefinition]:
    """Return top-level field definitions (parent_id IS NULL) for a given type."""
    q = select(FieldDefinition).where(
        FieldDefinition.target_type == target_type,
        FieldDefinition.is_deleted.is_(False),
        FieldDefinition.parent_id.is_(None),
    )
    if target_subtype:
        q = q.where(
            or_(FieldDefinition.target_subtype.is_(None), FieldDefinition.target_subtype == target_subtype)
        )
    result = await db.execute(q.order_by(FieldDefinition.sort_order))
    return list(result.scalars().all())


async def get_sub_field_definitions(
    db: AsyncSession, parent_id: uuid.UUID
) -> list[FieldDefinition]:
    """Return sub-field definitions for a group field."""
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.parent_id == parent_id,
            FieldDefinition.is_deleted.is_(False),
        ).order_by(FieldDefinition.sort_order)
    )
    return list(result.scalars().all())


def _validate_pid_value(value: object, settings: dict[str, Any], field_name: str) -> str | None:
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


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlsplit(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _validate_url_value(value: object, field_name: str) -> str | None:
    """Validate a single URL dict {"value": "https://...", "label": "optional"}. Returns error or None."""
    if not isinstance(value, dict):
        return f"Feld '{field_name}': URL muss ein Objekt {{value, label}} sein."
    if not _is_http_url(value.get("value")):
        return f"Feld '{field_name}': URL-Wert (value) muss eine vollständige http(s)-URL sein."
    label = value.get("label")
    if label is not None and not isinstance(label, str):
        return f"Feld '{field_name}': Linktitel (label) muss Text sein."
    return None


def protect_pid_fields(
    fields: list[FieldDefinition],
    metadata: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """PID fields are system-managed: keep stored values, drop manual input.

    Returns a copy of ``metadata`` where every pid field carries the stored
    value from ``existing`` (if any); client-supplied pid values are ignored.
    Only the PID mint endpoints and publish auto-minting may write pid fields.
    """
    protected = dict(metadata)
    for field in fields:
        if field.field_type != "pid":
            continue
        if existing is not None and existing.get(field.name) not in (None, "", []):
            protected[field.name] = deepcopy(existing[field.name])
        else:
            protected.pop(field.name, None)
    return protected


def _validate_relation_structure(value: object, field_name: str) -> str | None:
    """Validate the structure of a single relation entry. Returns error or None."""
    if not isinstance(value, dict):
        return f"Feld '{field_name}': Relation muss ein Objekt {{id, label, relation_type}} sein."
    entry_id = value.get("id")
    if not entry_id:
        return f"Feld '{field_name}': Relation-Eintrag muss eine 'id' enthalten."
    try:
        uuid.UUID(str(entry_id))
    except (ValueError, AttributeError):
        return f"Feld '{field_name}': '{entry_id}' ist keine gültige UUID."
    if not value.get("label"):
        return f"Feld '{field_name}': Relation-Eintrag muss ein 'label' enthalten."
    return None


def _validate_fixed_relation_type(value: dict[str, Any], field_name: str, settings: dict[str, Any]) -> str | None:
    fixed = settings.get("fixed_relation_type")
    if fixed and value.get("relation_type") != fixed:
        return f"Feld '{field_name}': Relationstyp muss '{fixed}' sein."
    return None


def _validate_authority_value(value: object, settings: dict[str, Any], field_name: str) -> str | None:
    """Validate one authority entry against the field's configured source."""
    if not isinstance(value, dict) or not all(
        isinstance(value.get(key), str) and value[key].strip()
        for key in ("source", "external_id", "label")
    ):
        return (
            f"Feld '{field_name}': Authority-Eintrag muss source, external_id und label enthalten."
        )
    if value["source"] != settings.get("source"):
        return f"Feld '{field_name}' verwendet die falsche Authority-Quelle."
    return None


async def _validate_relation_target(
    value: dict[str, Any], field_name: str, settings: dict[str, Any], db: AsyncSession
) -> str | None:
    """Check that the referenced UUID exists in the configured target table. Returns error or None."""
    target_type = settings.get("target_type")
    if not target_type:
        return None
    from katalon.core.models import Entity, Object, Occurrence, Place, Procedure

    model_map: dict[str, type[Object] | type[Entity] | type[Place] | type[Occurrence] | type[Procedure]] = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
        "procedure": Procedure,
    }
    model = model_map.get(target_type)
    if model is None:
        return None
    try:
        record_uuid = uuid.UUID(str(value["id"]))
    except (ValueError, KeyError):
        return None
    result = await db.execute(select(model).where(model.id == record_uuid))
    if result.scalar_one_or_none() is None:
        return f"Feld '{field_name}': Datensatz '{value['id']}' nicht gefunden in '{target_type}'."
    return None


async def validate_metadata(
    db: AsyncSession, record_type: str, metadata: dict[str, Any], target_subtype: str | None = None,
    *, skip_required: bool = False,
) -> list[str]:
    """Return list of validation error messages (empty = valid)."""
    fields = await get_field_definitions(db, record_type, target_subtype)
    errors: list[str] = []

    for field in fields:
        value = metadata.get(field.name)

        if not skip_required and field.is_required and (value is None or value == "" or value == []):
            errors.append(f"Feld '{field.name}' ist erforderlich.")
            continue

        if value is None:
            continue

        if field.field_type == "group":
            if not isinstance(value, list):
                errors.append(f"Feld '{field.name}': Containerfeld muss eine Liste sein.")
                continue
            sub_fields = await get_sub_field_definitions(db, field.id)
            for idx, instance in enumerate(value):
                if not isinstance(instance, dict):
                    errors.append(
                        f"Feld '{field.name}' (Eintrag {idx + 1}): Eintrag muss ein Objekt sein."
                    )
                    continue
                for sf in sub_fields:
                    sv = instance.get(sf.name)
                    field_path = f"{field.name}.{sf.name}"
                    indexed_prefix = f"Feld '{field_path}' (Eintrag {idx + 1})"
                    if not skip_required and sf.is_required and (sv is None or sv == ""):
                        errors.append(
                            f"{indexed_prefix}: Pflichtfeld."
                        )
                    if sv is not None and sf.field_type == "text":
                        regex = sf.settings.get("validation_regex")
                        if regex and isinstance(sv, str):
                            try:
                                if not re.fullmatch(regex, sv):
                                    errors.append(
                                        f"{indexed_prefix}: "
                                        "entspricht nicht dem erwarteten Format."
                                    )
                            except re.error:
                                pass
                    if sv is not None and sv != "" and sf.field_type == "date" and not _is_valid_date(sv):
                        errors.append(
                            f"{indexed_prefix}: Ungültiges Datum. Erlaubt: JJJJ, JJJJ-MM, JJJJ-MM-TT, -JJJJ (v. Chr.), mit ~ (circa) / ? (unsicher), oder Zeitraum START/ENDE."
                        )
                    if sv is not None and sf.field_type == "relation":
                        struct_err = _validate_relation_structure(
                            sv, field_path
                        )
                        if struct_err:
                            errors.append(struct_err.replace(f"Feld '{field_path}'", indexed_prefix, 1))
                            continue
                        type_err = _validate_fixed_relation_type(sv, field_path, sf.settings)
                        if type_err:
                            errors.append(type_err.replace(f"Feld '{field_path}'", indexed_prefix, 1))
                            continue
                        target_err = await _validate_relation_target(
                            sv, field_path, sf.settings, db
                        )
                        if target_err:
                            errors.append(target_err.replace(f"Feld '{field_path}'", indexed_prefix, 1))
                    if sv is not None and sf.field_type == "authority":
                        authority_err = _validate_authority_value(sv, sf.settings, field_path)
                        if authority_err:
                            errors.append(
                                authority_err.replace(f"Feld '{field_path}'", indexed_prefix, 1)
                            )
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

        if field.field_type == "url":
            if field.is_repeatable:
                if not isinstance(value, list):
                    errors.append(f"Feld '{field.name}' muss eine Liste sein (wiederholbar).")
                else:
                    for item in value:
                        err = _validate_url_value(item, field.name)
                        if err:
                            errors.append(err)
            else:
                err = _validate_url_value(value, field.name)
                if err:
                    errors.append(err)
            continue

        if field.field_type == "relation":
            if field.is_repeatable:
                if not isinstance(value, list):
                    errors.append(f"Feld '{field.name}' muss eine Liste sein (wiederholbar).")
                    continue
                items = value
            else:
                items = [value]
            for item in items:
                struct_err = _validate_relation_structure(item, field.name)
                if struct_err:
                    errors.append(struct_err)
                    continue
                type_err = _validate_fixed_relation_type(item, field.name, field.settings)
                if type_err:
                    errors.append(type_err)
                    continue
                target_err = await _validate_relation_target(item, field.name, field.settings, db)
                if target_err:
                    errors.append(target_err)
            continue

        if field.field_type == "authority":
            if field.is_repeatable:
                if not isinstance(value, list):
                    errors.append(f"Feld '{field.name}' muss eine Liste sein (wiederholbar).")
                    continue
                items = value
            else:
                if isinstance(value, list):
                    errors.append(f"Feld '{field.name}' darf keine Liste sein (nicht wiederholbar).")
                    continue
                items = [value]
            for item in items:
                authority_err = _validate_authority_value(item, field.settings, field.name)
                if authority_err:
                    errors.append(authority_err)
            continue

        if field.is_translatable:
            if not isinstance(value, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in value.items()
            ):
                errors.append(
                    f"Feld '{field.name}': Übersetzbarer Wert muss ein Objekt {{sprache: text}} sein."
                )
            continue

        if field.field_type == "date":
            items = value if field.is_repeatable and isinstance(value, list) else [value]
            for item in items:
                if item is None or item == "":
                    continue
                if not _is_valid_date(item):
                    errors.append(
                        f"Feld '{field.name}': Ungültiges Datum. Erlaubt: JJJJ, JJJJ-MM, JJJJ-MM-TT, -JJJJ (v. Chr.), mit ~ (circa) / ? (unsicher), oder Zeitraum START/ENDE."
                    )
                    break
            continue

        if record_type == "vocabulary_term":
            items = (
                value
                if field.is_repeatable and isinstance(value, list)
                else ([] if field.is_repeatable else [value])
            )
            for item in items:
                if field.field_type == "text" and not isinstance(item, str):
                    errors.append(f"Feld '{field.name}' muss Text enthalten.")
                elif field.field_type == "number" and (
                    not isinstance(item, (int, float)) or isinstance(item, bool)
                ):
                    errors.append(f"Feld '{field.name}' muss eine Zahl enthalten.")
                elif field.field_type == "boolean" and not isinstance(item, bool):
                    errors.append(f"Feld '{field.name}' muss einen Boolean enthalten.")
        if field.is_repeatable:
            if not isinstance(value, list):
                errors.append(f"Feld '{field.name}' muss eine Liste sein (wiederholbar).")
            else:
                regex = field.settings.get("validation_regex")
                if regex and field.field_type == "text":
                    for idx, item in enumerate(value):
                        if isinstance(item, str) and not re.fullmatch(regex, item):
                            errors.append(f"Feld '{field.name}' (Wert {idx + 1}): entspricht nicht dem erwarteten Format.")
        else:
            if isinstance(value, list):
                errors.append(f"Feld '{field.name}' darf keine Liste sein (nicht wiederholbar).")
            else:
                regex = field.settings.get("validation_regex")
                if regex and field.field_type == "text" and isinstance(value, str):
                    if not re.fullmatch(regex, value):
                        errors.append(f"Feld '{field.name}': entspricht nicht dem erwarteten Format.")

    return errors


async def prepare_metadata(
    db: AsyncSession,
    record_type: str,
    metadata: dict[str, Any],
    target_subtype: str | None = None,
    *,
    existing: dict[str, Any] | None = None,
    can_edit_locked: bool = False,
) -> dict[str, Any]:
    """Apply schema defaults, protect locked and system-managed fields."""
    prepared = deepcopy(metadata)
    fields = await get_field_definitions(db, record_type, target_subtype)
    for field in fields:
        settings = field.settings or {}
        if settings.get("is_locked") and not can_edit_locked:
            if existing is not None and field.name in existing:
                prepared[field.name] = deepcopy(existing[field.name])
                continue
            prepared.pop(field.name, None)
        if (
            field.field_type in {"text", "vocab", "vocab_free", "date", "number"}
            and prepared.get(field.name) in (None, "", [])
            and "default_value" in settings
        ):
            prepared[field.name] = deepcopy(settings["default_value"])
    # PID fields are system-managed: keep stored values, drop manual input —
    # regardless of editor role. Only the mint endpoints and publish auto-minting
    # may write them (see pid_service).
    return protect_pid_fields(fields, prepared, existing)
