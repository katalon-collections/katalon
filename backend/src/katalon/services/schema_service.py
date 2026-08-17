from __future__ import annotations

import re
import uuid
from copy import deepcopy
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition


def _is_valid_date(value: object) -> bool:
    """Accept ISO years, year-months, and real calendar dates."""
    if not isinstance(value, str):
        return False
    if re.fullmatch(r"\d{4}", value):
        return True
    month = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if month:
        return 1 <= int(month.group(2)) <= 12
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


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


def _validate_fixed_relation_type(value: dict, field_name: str, settings: dict) -> str | None:
    fixed = settings.get("fixed_relation_type")
    if fixed and value.get("relation_type") != fixed:
        return f"Feld '{field_name}': Relationstyp muss '{fixed}' sein."
    return None


def _validate_authority_value(value: object, settings: dict, field_name: str) -> str | None:
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
    value: dict, field_name: str, settings: dict, db: AsyncSession
) -> str | None:
    """Check that the referenced UUID exists in the configured target table. Returns error or None."""
    target_type = settings.get("target_type")
    if not target_type:
        return None
    from katalon.core.models import Entity, Object, Occurrence, Place, Procedure

    model_map = {
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
    db: AsyncSession, record_type: str, metadata: dict, target_subtype: str | None = None,
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
                    if sv is not None and sf.field_type == "date" and not _is_valid_date(sv):
                        errors.append(
                            f"{indexed_prefix}: Ungültiges Datum. Erlaubt: JJJJ, JJJJ-MM oder JJJJ-MM-TT."
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
                if not _is_valid_date(item):
                    errors.append(
                        f"Feld '{field.name}': Ungültiges Datum. Erlaubt: JJJJ, JJJJ-MM oder JJJJ-MM-TT."
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
    metadata: dict,
    target_subtype: str | None = None,
    *,
    existing: dict | None = None,
    can_edit_locked: bool = False,
) -> dict:
    """Apply schema defaults and protect locked fields."""
    prepared = deepcopy(metadata)
    for field in await get_field_definitions(db, record_type, target_subtype):
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
    return prepared
