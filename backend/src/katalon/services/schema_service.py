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

from katalon.core.models import FieldDefinition, VocabularyTerm


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


def _parse_localized_number(value: object) -> tuple[bool, int | float | None]:
    """Parse a numeric value or localized string (e.g. '10.000,65' -> 10000.65, '23,5' -> 23.5)."""
    if value is None or value == "":
        return True, None
    if isinstance(value, bool):
        return False, None
    if isinstance(value, (int, float)):
        return True, value
    if not isinstance(value, str):
        return False, None

    s = value.strip()
    if not s:
        return True, None

    sign = ""
    if s.startswith(("-", "+")):
        sign = s[0]
        s = s[1:]

    # Any remaining sign is invalid (e.g. "23-3")
    if "-" in s or "+" in s:
        return False, None

    # Check for scientific notation fallback (e.g. "1e-3" or "1.5e4")
    if ("e" in s.lower()) and ("," not in s):
        try:
            return True, float(sign + s)
        except ValueError:
            return False, None

    # Only digits, dots, commas allowed
    if not all(c.isdigit() or c in ".," for c in s):
        return False, None

    has_dot = "." in s
    has_comma = "," in s

    if has_dot and has_comma:
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        if last_comma > last_dot:
            # German notation: 10.000,65
            parts = s[:last_comma].split(".")
            if not parts[0].isdigit() or not (1 <= len(parts[0]) <= 3):
                return False, None
            for p in parts[1:]:
                if len(p) != 3 or not p.isdigit():
                    return False, None
            dec = s[last_comma + 1:]
            if not dec.isdigit():
                return False, None
            try:
                return True, float(sign + "".join(parts) + "." + dec)
            except ValueError:
                return False, None
        else:
            # US notation: 10,000.65
            parts = s[:last_dot].split(",")
            if not parts[0].isdigit() or not (1 <= len(parts[0]) <= 3):
                return False, None
            for p in parts[1:]:
                if len(p) != 3 or not p.isdigit():
                    return False, None
            dec = s[last_dot + 1:]
            if not dec.isdigit():
                return False, None
            try:
                return True, float(sign + "".join(parts) + "." + dec)
            except ValueError:
                return False, None
    elif has_comma:
        comma_count = s.count(",")
        if comma_count == 1:
            int_part, dec_part = s.split(",")
            if not int_part.isdigit() or not dec_part.isdigit():
                return False, None
            try:
                return True, float(sign + int_part + "." + dec_part)
            except ValueError:
                return False, None
        else:
            parts = s.split(",")
            if not parts[0].isdigit() or not (1 <= len(parts[0]) <= 3):
                return False, None
            for p in parts[1:]:
                if len(p) != 3 or not p.isdigit():
                    return False, None
            try:
                return True, int(sign + "".join(parts))
            except ValueError:
                return False, None
    elif has_dot:
        dot_count = s.count(".")
        if dot_count == 1:
            int_part, dec_part = s.split(".")
            if not int_part.isdigit() or not dec_part.isdigit():
                return False, None
            try:
                return True, float(sign + int_part + "." + dec_part)
            except ValueError:
                return False, None
        else:
            parts = s.split(".")
            if not parts[0].isdigit() or not (1 <= len(parts[0]) <= 3):
                return False, None
            for p in parts[1:]:
                if len(p) != 3 or not p.isdigit():
                    return False, None
            try:
                return True, int(sign + "".join(parts))
            except ValueError:
                return False, None
    else:
        if not s.isdigit():
            return False, None
        try:
            return True, int(sign + s)
        except ValueError:
            return False, None


def _is_valid_number(value: object) -> bool:
    """Check if value is a valid numeric value (int, float, or parseable numeric string)."""
    valid, _ = _parse_localized_number(value)
    return valid and (value is not None and value != "")


def _coerce_number(value: object) -> Any:
    """Coerce value to int, float, or None if empty. Return unchanged if invalid."""
    valid, parsed = _parse_localized_number(value)
    if valid:
        return parsed
    return value


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
            or_(
                FieldDefinition.target_subtype.is_(None),
                FieldDefinition.target_subtype == target_subtype,
            )
        )
    result = await db.execute(q.order_by(FieldDefinition.sort_order))
    return list(result.scalars().all())


async def get_sub_field_definitions(
    db: AsyncSession, parent_id: uuid.UUID
) -> list[FieldDefinition]:
    """Return sub-field definitions for a group field."""
    result = await db.execute(
        select(FieldDefinition)
        .where(
            FieldDefinition.parent_id == parent_id,
            FieldDefinition.is_deleted.is_(False),
        )
        .order_by(FieldDefinition.sort_order)
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
    if not value.get("value"):
        return None
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


def _validate_fixed_relation_type(
    value: dict[str, Any], field_name: str, settings: dict[str, Any]
) -> str | None:
    fixed = settings.get("fixed_relation_type")
    if fixed and value.get("relation_type") != fixed:
        return f"Feld '{field_name}': Relationstyp muss '{fixed}' sein."
    return None


def _validate_authority_value(
    value: object, settings: dict[str, Any], field_name: str
) -> str | None:
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


def _is_reference_in_existing(
    existing: dict[str, Any] | None, field_path: str, ref_id: uuid.UUID
) -> bool:
    """Check if ref_id was already present in existing metadata for field_path."""
    if not existing:
        return False
    parts = field_path.split(".")
    target_id_str = str(ref_id).lower()
    if len(parts) == 1:
        val = existing.get(parts[0])
        if isinstance(val, dict):
            return str(val.get("id", "")).lower() == target_id_str
        if isinstance(val, list):
            return any(
                isinstance(item, dict) and str(item.get("id", "")).lower() == target_id_str
                for item in val
            )
        return False
    if len(parts) == 2:
        parent_val = existing.get(parts[0])
        if isinstance(parent_val, list):
            for instance in parent_val:
                if isinstance(instance, dict):
                    sub_val = instance.get(parts[1])
                    if isinstance(sub_val, dict) and str(sub_val.get("id", "")).lower() == target_id_str:
                        return True
                    if isinstance(sub_val, list) and any(
                        isinstance(item, dict) and str(item.get("id", "")).lower() == target_id_str
                        for item in sub_val
                    ):
                        return True
        return False
    return False


async def _validate_relation_target(
    value: dict[str, Any],
    field_name: str,
    settings: dict[str, Any],
    db: AsyncSession,
    existing: dict[str, Any] | None = None,
) -> str | None:
    """Check that the referenced UUID exists in the configured target table and is not deleted.

    Returns error message or None.
    """
    target_type = settings.get("target_type")
    if not target_type:
        return None
    from katalon.services.relation_service import _RECORD_MODELS, validate_relation_endpoint

    if target_type not in _RECORD_MODELS:
        return None
    try:
        record_uuid = uuid.UUID(str(value["id"]))
    except (ValueError, KeyError):
        return None

    if existing and _is_reference_in_existing(existing, field_name, record_uuid):
        return None

    endpoint_error = await validate_relation_endpoint(db, target_type, record_uuid)
    if endpoint_error is not None:
        return f"Feld '{field_name}': Datensatz '{value['id']}' nicht gefunden in '{target_type}'."
    return None


async def _validate_vocab_value(
    db: AsyncSession,
    value: object,
    field_name: str,
    settings: dict[str, Any],
    existing: dict[str, Any] | None = None,
) -> str | None:
    """Validate one controlled-vocabulary reference against its configured vocabulary."""
    if not isinstance(value, dict):
        return f"Feld '{field_name}': Vokabularwert muss ein Objekt {{id, label}} sein."
    try:
        term_id = uuid.UUID(str(value.get("id")))
        vocab_id = uuid.UUID(str(settings["vocabulary_id"]))
    except (KeyError, ValueError, TypeError):
        return f"Feld '{field_name}': Vokabularwert enthält keine gültige Term-ID."

    # If this term reference was already present on the record, keep it even if
    # the term was deleted (force-delete without remapping).
    if existing and _is_reference_in_existing(existing, field_name, term_id):
        return None

    exists = await db.scalar(
        select(VocabularyTerm.id).where(
            VocabularyTerm.id == term_id, VocabularyTerm.vocabulary_id == vocab_id
        )
    )
    if exists is None:
        return f"Feld '{field_name}': Vokabularterm nicht gefunden."
    return None


async def validate_metadata(
    db: AsyncSession,
    record_type: str,
    metadata: dict[str, Any],
    target_subtype: str | None = None,
    *,
    existing: dict[str, Any] | None = None,
    skip_required: bool = False,
) -> list[str]:
    """Return list of validation error messages (empty = valid)."""
    fields = await get_field_definitions(db, record_type, target_subtype)
    errors: list[str] = []

    for field in fields:
        if field.name == "idno":
            # 'idno' is a native model column (see _ensure_idno_fields in main.py),
            # never part of metadata_. Its own requiredness/pattern is enforced at
            # the API layer against the dedicated column, not here.
            continue
        value = metadata.get(field.name)

        if (
            not skip_required
            and field.is_required
            and (value is None or value == "" or value == [])
        ):
            errors.append(f"Feld '{field.name}' ist erforderlich.")
            continue

        if value is None or value == "":
            continue

        if field.is_repeatable and isinstance(value, list):
            max_count = (field.settings or {}).get("max_count")
            if isinstance(max_count, int) and len(value) > max_count:
                errors.append(f"Feld '{field.name}': maximal {max_count} Einträge erlaubt.")

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
                        errors.append(f"{indexed_prefix}: Pflichtfeld.")
                    if sv is not None and sf.field_type == "text":
                        regex = sf.settings.get("validation_regex")
                        if regex and isinstance(sv, str):
                            try:
                                if not re.fullmatch(regex, sv):
                                    errors.append(
                                        f"{indexed_prefix}: entspricht nicht dem erwarteten Format."
                                    )
                            except re.error:
                                pass
                    if (
                        sv is not None
                        and sv != ""
                        and sf.field_type == "date"
                        and not _is_valid_date(sv)
                    ):
                        errors.append(
                            f"{indexed_prefix}: Ungültiges Datum. Erlaubt: JJJJ, JJJJ-MM, JJJJ-MM-TT, -JJJJ (v. Chr.), mit ~ (circa) / ? (unsicher), oder Zeitraum START/ENDE."
                        )
                    if sv is not None and sf.field_type == "relation":
                        struct_err = _validate_relation_structure(sv, field_path)
                        if struct_err:
                            errors.append(
                                struct_err.replace(f"Feld '{field_path}'", indexed_prefix, 1)
                            )
                            continue
                        type_err = _validate_fixed_relation_type(sv, field_path, sf.settings)
                        if type_err:
                            errors.append(
                                type_err.replace(f"Feld '{field_path}'", indexed_prefix, 1)
                            )
                            continue
                        target_err = await _validate_relation_target(
                            sv, field_path, sf.settings, db, existing=existing
                        )
                        if target_err:
                            errors.append(
                                target_err.replace(f"Feld '{field_path}'", indexed_prefix, 1)
                            )
                    if sv is not None and sf.field_type == "authority":
                        authority_err = _validate_authority_value(sv, sf.settings, field_path)
                        if authority_err:
                            errors.append(
                                authority_err.replace(f"Feld '{field_path}'", indexed_prefix, 1)
                            )
                    if (
                        sv is not None
                        and sv != ""
                        and sf.field_type == "number"
                        and not _is_valid_number(sv)
                    ):
                        errors.append(f"{indexed_prefix}: muss eine Zahl enthalten.")
                    if sv is not None and sf.field_type == "boolean" and not isinstance(sv, bool):
                        errors.append(f"{indexed_prefix}: muss einen Boolean enthalten.")
                    if sv is not None and sf.field_type == "vocab_free" and not isinstance(sv, str):
                        errors.append(f"{indexed_prefix}: muss Text enthalten.")
                    if sv is not None and sf.field_type == "geo" and not isinstance(sv, str):
                        errors.append(f"{indexed_prefix}: muss Text enthalten.")
                    if sv is not None and sf.field_type == "vocab":
                        vocab_err = await _validate_vocab_value(
                            db, sv, field_path, sf.settings, existing=existing
                        )
                        if vocab_err:
                            errors.append(
                                vocab_err.replace(f"Feld '{field_path}'", indexed_prefix, 1)
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
                target_err = await _validate_relation_target(
                    item, field.name, field.settings, db, existing=existing
                )
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
                    errors.append(
                        f"Feld '{field.name}' darf keine Liste sein (nicht wiederholbar)."
                    )
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

        if field.field_type in {"number", "boolean", "vocab_free", "geo", "vocab"}:
            items = value if field.is_repeatable and isinstance(value, list) else [value]
            for item in items:
                if field.field_type == "number":
                    if item is None or item == "":
                        continue
                    if not _is_valid_number(item):
                        errors.append(f"Feld '{field.name}' muss eine Zahl enthalten.")
                elif field.field_type == "boolean" and not isinstance(item, bool):
                    errors.append(f"Feld '{field.name}' muss einen Boolean enthalten.")
                elif field.field_type in {"vocab_free", "geo"} and not isinstance(item, str):
                    errors.append(f"Feld '{field.name}' muss Text enthalten.")
                elif field.field_type == "vocab":
                    vocab_err = await _validate_vocab_value(
                        db, item, field.name, field.settings, existing=existing
                    )
                    if vocab_err:
                        errors.append(vocab_err)
        if field.is_repeatable:
            if not isinstance(value, list):
                errors.append(f"Feld '{field.name}' muss eine Liste sein (wiederholbar).")
            else:
                regex = field.settings.get("validation_regex")
                if regex and field.field_type == "text":
                    for idx, item in enumerate(value):
                        if isinstance(item, str) and not re.fullmatch(regex, item):
                            errors.append(
                                f"Feld '{field.name}' (Wert {idx + 1}): entspricht nicht dem erwarteten Format."
                            )
        else:
            if isinstance(value, list):
                errors.append(f"Feld '{field.name}' darf keine Liste sein (nicht wiederholbar).")
            else:
                regex = field.settings.get("validation_regex")
                if regex and field.field_type == "text" and isinstance(value, str):
                    if not re.fullmatch(regex, value):
                        errors.append(
                            f"Feld '{field.name}': entspricht nicht dem erwarteten Format."
                        )

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
        if field.field_type == "number" and field.name in prepared:
            val = prepared[field.name]
            if field.is_repeatable:
                if isinstance(val, list):
                    prepared[field.name] = [
                        _coerce_number(item)
                        for item in val
                        if item is not None and item != ""
                    ]
            else:
                prepared[field.name] = _coerce_number(val)
        if field.field_type == "group" and field.name in prepared:
            group_val = prepared[field.name]
            if isinstance(group_val, list):
                sub_fields = await get_sub_field_definitions(db, field.id)
                num_sub_fields = {sf.name for sf in sub_fields if sf.field_type == "number"}
                if num_sub_fields:
                    for instance in group_val:
                        if isinstance(instance, dict):
                            for sf_name in num_sub_fields:
                                if sf_name in instance:
                                    instance[sf_name] = _coerce_number(instance[sf_name])
    # PID fields are system-managed: keep stored values, drop manual input —
    # regardless of editor role. Only the mint endpoints and publish auto-minting
    # may write them (see pid_service).
    return protect_pid_fields(fields, prepared, existing)


def _is_value_present(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (int, float, bool)):
        return True
    if isinstance(val, list):
        return any(_is_value_present(item) for item in val)
    if isinstance(val, dict):
        return any(_is_value_present(v) for v in val.values())
    return True


def get_target_model(target_type: str) -> Any | None:
    from katalon.services.relation_service import _RECORD_MODELS

    model = _RECORD_MODELS.get(target_type)
    if model is not None:
        return model
    if target_type == "vocabulary_term":
        return VocabularyTerm
    return None


async def count_field_usage(db: AsyncSession, field: FieldDefinition) -> int:
    """Count active records of the field's target_type that have a non-empty value for this field."""
    model = get_target_model(field.target_type)
    if model is None:
        return 0

    parent = None
    if field.parent_id is not None:
        parent = await db.get(FieldDefinition, field.parent_id)

    check_key = parent.name if parent else field.name

    query = select(model.metadata_).where(model.metadata_.has_key(check_key))
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))

    result = await db.execute(query)
    records = result.scalars().all()

    count = 0
    for metadata in records:
        if not metadata or not isinstance(metadata, dict):
            continue
        if parent:
            instances = metadata.get(parent.name)
            if isinstance(instances, list):
                if any(
                    isinstance(inst, dict) and _is_value_present(inst.get(field.name))
                    for inst in instances
                ):
                    count += 1
        else:
            if _is_value_present(metadata.get(field.name)):
                count += 1

    return count


async def purge_field_data(
    db: AsyncSession,
    field: FieldDefinition,
    user_id: uuid.UUID | None = None,
) -> int:
    """Purge all stored values of `field` from records of `field.target_type`.

    For a top-level field, removes `field.name` from record metadata.
    For a subfield of a group, removes `field.name` from each dictionary in the parent's group array.
    Synchronizes schema-derived relations if the field or its parent is a relation/group.
    Writes an audit log entry for affected records where supported.
    Returns the count of records modified.
    """
    from sqlalchemy.orm.attributes import flag_modified

    from katalon.services.audit_service import log_change

    model = get_target_model(field.target_type)
    if model is None:
        return 0

    parent = None
    if field.parent_id is not None:
        parent = await db.get(FieldDefinition, field.parent_id)

    check_key = parent.name if parent else field.name

    query = select(model).where(model.metadata_.has_key(check_key))
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))

    result = await db.execute(query)
    records = list(result.scalars().all())

    modified_count = 0
    records_to_sync_relations: list[Any] = []

    for record in records:
        if not record.metadata_ or not isinstance(record.metadata_, dict):
            continue

        changed = False
        if parent:
            instances = record.metadata_.get(parent.name)
            if isinstance(instances, list):
                for inst in instances:
                    if isinstance(inst, dict) and field.name in inst:
                        del inst[field.name]
                        changed = True
        else:
            if field.name in record.metadata_:
                del record.metadata_[field.name]
                changed = True

        if changed:
            flag_modified(record, "metadata_")
            modified_count += 1
            if field.field_type in ("relation", "group") or (
                parent and parent.field_type == "group"
            ):
                records_to_sync_relations.append(record)

            if field.target_type != "vocabulary_term":
                await log_change(
                    db,
                    record_type=field.target_type,
                    record_id=record.id,
                    user_id=user_id,
                    action="field_data_purged",
                    changed_fields={"purged_field": field.name},
                )

    if records_to_sync_relations and field.target_type != "vocabulary_term":
        from katalon.services.relation_service import sync_schema_relations

        for rec in records_to_sync_relations:
            await sync_schema_relations(db, field.target_type, rec.id, rec.metadata_)

    return modified_count


async def migrate_translatable_shape(
    db: AsyncSession,
    field: FieldDefinition,
    *,
    enable: bool,
    primary_language: str,
    user_id: uuid.UUID | None = None,
) -> int:
    """Reshape existing values of a top-level text/richtext field after its
    ``is_translatable`` flag changed, so the schema and the stored data never
    drift apart (#399 — a field toggled translatable left legacy plain-string
    values unreadable; toggling it off left `{lang: text}` objects invalid).

    Enabling (``enable=True``): wraps a legacy plain-string value into
    ``{primary_language: value}``. Lossless — every character is kept.

    Disabling (``enable=False``): collapses a ``{lang: text}`` value back to a
    plain string, keeping ``primary_language``'s text (or the first non-empty
    language if the primary one is empty) and discarding every other
    language. Callers MUST warn the admin before triggering this direction —
    text in the dropped languages is not recoverable from the database.

    Returns the number of records whose value was reshaped.
    """
    from sqlalchemy.orm.attributes import flag_modified

    from katalon.services.audit_service import log_change

    model = get_target_model(field.target_type)
    if model is None:
        return 0

    query = select(model).where(model.metadata_.has_key(field.name))
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))

    result = await db.execute(query)
    records = list(result.scalars().all())

    migrated = 0
    for record in records:
        if not record.metadata_ or not isinstance(record.metadata_, dict):
            continue
        val = record.metadata_.get(field.name)
        if enable:
            if not isinstance(val, str) or not val.strip():
                continue
            record.metadata_[field.name] = {primary_language: val}
        else:
            if not isinstance(val, dict):
                continue
            text = val.get(primary_language) or next(
                (v for v in val.values() if isinstance(v, str) and v.strip()), ""
            )
            record.metadata_[field.name] = text

        flag_modified(record, "metadata_")
        migrated += 1
        if field.target_type != "vocabulary_term":
            await log_change(
                db,
                record_type=field.target_type,
                record_id=record.id,
                user_id=user_id,
                action="field_shape_migrated",
                changed_fields={
                    "field": field.name,
                    "direction": "translatable_on" if enable else "translatable_off",
                },
            )

    return migrated


async def migrate_repeatable_shape(
    db: AsyncSession,
    field: FieldDefinition,
    *,
    enable: bool,
    user_id: uuid.UUID | None = None,
) -> int:
    """Reshape existing values of a top-level field after its ``is_repeatable``
    flag changed (#399 — same drift-prevention as migrate_translatable_shape;
    subfields of a group are out of scope, group fields are always repeatable).

    Enabling (``enable=True``): wraps a scalar value into ``[value]``. Lossless.

    Disabling (``enable=False``): collapses a list back to its first entry.
    Every other entry is discarded. Callers MUST warn the admin before
    triggering this direction — see ``count_repeatable_collapse_loss``.

    Returns the number of records whose value was reshaped.
    """
    from sqlalchemy.orm.attributes import flag_modified

    from katalon.services.audit_service import log_change

    model = get_target_model(field.target_type)
    if model is None:
        return 0

    query = select(model).where(model.metadata_.has_key(field.name))
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))

    result = await db.execute(query)
    records = list(result.scalars().all())

    migrated = 0
    for record in records:
        if not record.metadata_ or not isinstance(record.metadata_, dict):
            continue
        val = record.metadata_.get(field.name)
        if enable:
            if isinstance(val, list) or val is None or val == "":
                continue
            record.metadata_[field.name] = [val]
        else:
            if not isinstance(val, list):
                continue
            record.metadata_[field.name] = val[0] if val else None

        flag_modified(record, "metadata_")
        migrated += 1
        if field.target_type != "vocabulary_term":
            await log_change(
                db,
                record_type=field.target_type,
                record_id=record.id,
                user_id=user_id,
                action="field_shape_migrated",
                changed_fields={
                    "field": field.name,
                    "direction": "repeatable_on" if enable else "repeatable_off",
                },
            )

    return migrated


async def count_repeatable_collapse_loss(db: AsyncSession, field: FieldDefinition) -> int:
    """Count records whose current list value for ``field`` holds more than one
    entry — i.e. how many would actually lose data if ``is_repeatable`` were
    disabled (collapsing to the first entry)."""
    model = get_target_model(field.target_type)
    if model is None:
        return 0
    query = select(model.metadata_).where(model.metadata_.has_key(field.name))
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    result = await db.execute(query)
    count = 0
    for metadata in result.scalars().all():
        if not isinstance(metadata, dict):
            continue
        val = metadata.get(field.name)
        if isinstance(val, list) and len(val) > 1:
            count += 1
    return count


# field_type pairs whose values are all plain strings — freely interchangeable,
# a change within this group can never make an existing value invalid.
_INTERCHANGEABLE_SCALAR_TYPES = {"text", "richtext", "vocab_free", "geo"}


async def count_field_type_change_risk(
    db: AsyncSession, field: FieldDefinition, new_field_type: str
) -> int:
    """Count existing records whose value may no longer fit ``new_field_type``.

    Unlike the is_translatable/is_repeatable migrations, a field_type change
    never touches stored values — there is no generally safe way to convert a
    plain string into e.g. a vocabulary reference. The record keeps exactly
    what it has; it just cannot be re-saved unmodified once the schema no
    longer matches. Returns 0 when the change stays within the interchangeable
    plain-text group, where nothing can become invalid.
    """
    if field.field_type == new_field_type:
        return 0
    if (
        field.field_type in _INTERCHANGEABLE_SCALAR_TYPES
        and new_field_type in _INTERCHANGEABLE_SCALAR_TYPES
    ):
        return 0
    return await count_field_usage(db, field)
