# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from katalon.core.models import AuditLog, ExportMappingRule, ExportMappingSet, FieldDefinition
from katalon.core.schemas import (
    ExportMappingRuleCreate,
    ExportMappingRuleUpdate,
    ExportMappingSetCreate,
    ExportMappingSetUpdate,
)
from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportRecordContext,
    MappingDiagnostic,
    MappingSpec,
    SourceKind,
)

OAI_DC_FORMAT = "oai_dc"

MappingIndex = dict[str, CompiledMappingSet]


class OptimisticLockError(Exception):
    """Raised when an update conflicts with the current version."""


# ---------------------------------------------------------------------------
# OAI-PMH & Export Query Helpers (only read published sets)
# ---------------------------------------------------------------------------


async def mapped_format_keys(db: AsyncSession) -> set[str]:
    """format_keys that have a published ExportMappingSet with at least one enabled rule."""
    result = await db.execute(
        select(ExportMappingSet.format_key)
        .join(ExportMappingRule, ExportMappingRule.mapping_set_id == ExportMappingSet.id)
        .where(
            ExportMappingSet.status == "published",
            ExportMappingRule.is_enabled.is_(True),
        )
        .distinct()
    )
    return set(result.scalars().all())


async def mapped_record_types(db: AsyncSession, format_key: str) -> set[str]:
    """Record types that have at least one enabled rule in a published set for format_key."""
    result = await db.execute(
        select(ExportMappingSet.record_type)
        .join(ExportMappingRule, ExportMappingRule.mapping_set_id == ExportMappingSet.id)
        .where(
            ExportMappingSet.format_key == format_key,
            ExportMappingSet.status == "published",
            ExportMappingRule.is_enabled.is_(True),
        )
        .distinct()
    )
    return set(result.scalars().all())


async def get_mapping_index(db: AsyncSession, format_key: str) -> MappingIndex:
    """Return mapping index for format_key compiled from all published sets."""
    result = await db.execute(
        select(ExportMappingSet)
        .options(selectinload(ExportMappingSet.rules))
        .where(
            ExportMappingSet.format_key == format_key,
            ExportMappingSet.status == "published",
        )
    )
    sets: dict[str, CompiledMappingSet] = {}
    for mapping_set in result.scalars().all():
        record_type = mapping_set.record_type
        rules: list[MappingSpec] = []
        for r in sorted(mapping_set.rules, key=lambda x: x.sort_order):
            if not r.is_enabled:
                continue
            sk = (
                SourceKind(r.source_kind)
                if r.source_kind in SourceKind._value2member_map_
                else SourceKind.FIELD
            )
            rules.append(
                MappingSpec(
                    rule_key=r.rule_key,
                    source_kind=sk,
                    source_config=dict(r.source_config or {}),
                    target_key=r.target_key,
                    settings=dict(r.settings or {}),
                    sort_order=r.sort_order,
                    is_enabled=r.is_enabled,
                )
            )
        sets[record_type] = CompiledMappingSet(
            format_key=format_key,
            record_type=record_type,
            rules=rules,
        )
    return sets


# ---------------------------------------------------------------------------
# Versioned ExportMappingSet Operations
# ---------------------------------------------------------------------------


async def list_mapping_sets(
    db: AsyncSession,
    *,
    record_type: str | None = None,
    format_key: str | None = None,
    status: str | None = None,
) -> list[ExportMappingSet]:
    q = select(ExportMappingSet).options(selectinload(ExportMappingSet.rules))
    if record_type:
        q = q.where(ExportMappingSet.record_type == record_type)
    if format_key:
        q = q.where(ExportMappingSet.format_key == format_key)
    if status:
        q = q.where(ExportMappingSet.status == status)
    q = q.order_by(
        ExportMappingSet.format_key,
        ExportMappingSet.record_type,
        ExportMappingSet.revision.desc(),
    )
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_mapping_set(db: AsyncSession, set_id: uuid.UUID) -> ExportMappingSet | None:
    result = await db.execute(
        select(ExportMappingSet)
        .options(selectinload(ExportMappingSet.rules))
        .where(ExportMappingSet.id == set_id)
    )
    return result.scalar_one_or_none()


async def create_mapping_set(
    db: AsyncSession,
    data: ExportMappingSetCreate,
    user_id: uuid.UUID | None = None,
) -> ExportMappingSet:
    """Create a draft mapping set. If based_on_id is provided, clone rules from base."""
    revision = 1
    rules_to_clone: list[ExportMappingRule] = []

    if data.based_on_id:
        base = await get_mapping_set(db, data.based_on_id)
        if base:
            revision = base.revision + 1
            rules_to_clone = base.rules

    new_set = ExportMappingSet(
        format_key=data.format_key,
        profile_id=data.profile_id,
        profile_version=data.profile_version,
        record_type=data.record_type,
        target_subtype=data.target_subtype,
        name=data.name,
        status="draft",
        revision=revision,
        based_on_id=data.based_on_id,
        institution_config=dict(data.institution_config or {}),
        version=1,
        created_by=user_id,
    )
    db.add(new_set)
    await db.flush()

    for r in rules_to_clone:
        cloned_rule = ExportMappingRule(
            rule_key=r.rule_key,  # Keep rule_key stable across revisions!
            mapping_set_id=new_set.id,
            source_kind=r.source_kind,
            field_definition_id=r.field_definition_id,
            source_config=dict(r.source_config or {}),
            target_key=r.target_key,
            settings=dict(r.settings or {}),
            sort_order=r.sort_order,
            is_enabled=r.is_enabled,
        )
        db.add(cloned_rule)

    await db.flush()

    # Log audit entry
    log = AuditLog(
        record_type="export_mapping_set",
        record_id=new_set.id,
        user_id=user_id,
        action="create",
        changed_fields={
            "name": new_set.name,
            "format_key": new_set.format_key,
            "record_type": new_set.record_type,
            "revision": new_set.revision,
            "status": "draft",
        },
    )
    db.add(log)
    await db.commit()

    return await get_mapping_set(db, new_set.id)  # type: ignore[return-value]


async def update_mapping_set(
    db: AsyncSession,
    set_id: uuid.UUID,
    data: ExportMappingSetUpdate,
    expected_version: int | None = None,
    user_id: uuid.UUID | None = None,
) -> ExportMappingSet:
    mapping_set = await get_mapping_set(db, set_id)
    if not mapping_set:
        raise ValueError("ExportMappingSet nicht gefunden.")
    if mapping_set.status != "draft":
        raise ValueError("Nur Entwürfe (status='draft') können direkt bearbeitet werden.")
    if expected_version is not None and mapping_set.version != expected_version:
        raise OptimisticLockError(
            f"Konflikt: Aktuelle Version ist {mapping_set.version}, erwartet wurde {expected_version}."
        )

    if data.name is not None:
        mapping_set.name = data.name
    if data.institution_config is not None:
        mapping_set.institution_config = dict(data.institution_config)

    mapping_set.version += 1
    mapping_set.updated_at = datetime.now(UTC).replace(tzinfo=None)

    log = AuditLog(
        record_type="export_mapping_set",
        record_id=mapping_set.id,
        user_id=user_id,
        action="update",
        changed_fields={"version": mapping_set.version, "name": mapping_set.name},
    )
    db.add(log)
    await db.commit()
    return mapping_set


async def delete_mapping_set(
    db: AsyncSession,
    set_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> None:
    mapping_set = await get_mapping_set(db, set_id)
    if not mapping_set:
        raise ValueError("ExportMappingSet nicht gefunden.")
    if mapping_set.status == "published":
        raise ValueError("Veröffentlichte Mapping-Sets können nicht direkt gelöscht werden.")

    log = AuditLog(
        record_type="export_mapping_set",
        record_id=mapping_set.id,
        user_id=user_id,
        action="delete",
        changed_fields={"name": mapping_set.name, "revision": mapping_set.revision},
    )
    db.add(log)
    await db.delete(mapping_set)
    await db.commit()


# ---------------------------------------------------------------------------
# Rule Operations on Draft Sets
# ---------------------------------------------------------------------------


async def create_rule(
    db: AsyncSession,
    set_id: uuid.UUID,
    data: ExportMappingRuleCreate,
) -> ExportMappingRule:
    mapping_set = await get_mapping_set(db, set_id)
    if not mapping_set:
        raise ValueError("ExportMappingSet nicht gefunden.")
    if mapping_set.status != "draft":
        raise ValueError("Regeln können nur zu Entwürfen (status='draft') hinzugefügt werden.")

    # Resolve field_name if field_definition_id provided
    source_cfg = dict(data.source_config or {})
    if data.field_definition_id and "field_name" not in source_cfg:
        field = await db.get(FieldDefinition, data.field_definition_id)
        if field:
            source_cfg["field_name"] = field.name
            source_cfg["field_type"] = field.field_type

    rule = ExportMappingRule(
        rule_key=data.rule_key or uuid.uuid4(),
        mapping_set_id=set_id,
        source_kind=data.source_kind.value if hasattr(data.source_kind, "value") else str(data.source_kind),
        field_definition_id=data.field_definition_id,
        source_config=source_cfg,
        target_key=data.target_key,
        settings=dict(data.settings or {}),
        sort_order=data.sort_order,
        is_enabled=data.is_enabled,
    )
    db.add(rule)
    mapping_set.version += 1
    mapping_set.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(rule)
    return rule


async def update_rule(
    db: AsyncSession,
    set_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: ExportMappingRuleUpdate,
) -> ExportMappingRule:
    mapping_set = await get_mapping_set(db, set_id)
    if not mapping_set:
        raise ValueError("ExportMappingSet nicht gefunden.")
    if mapping_set.status != "draft":
        raise ValueError("Regeln können nur in Entwürfen bearbeitet werden.")

    result = await db.execute(
        select(ExportMappingRule).where(
            ExportMappingRule.id == rule_id,
            ExportMappingRule.mapping_set_id == set_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise ValueError("ExportMappingRule nicht gefunden.")

    if data.source_kind is not None:
        rule.source_kind = (
            data.source_kind.value if hasattr(data.source_kind, "value") else str(data.source_kind)
        )
    if data.field_definition_id is not None:
        rule.field_definition_id = data.field_definition_id
        field = await db.get(FieldDefinition, data.field_definition_id)
        if field:
            rule.source_config = {
                **dict(rule.source_config or {}),
                "field_name": field.name,
                "field_type": field.field_type,
            }
    if data.source_config is not None:
        rule.source_config = dict(data.source_config)
    if data.target_key is not None:
        rule.target_key = data.target_key
    if data.settings is not None:
        rule.settings = dict(data.settings)
    if data.sort_order is not None:
        rule.sort_order = data.sort_order
    if data.is_enabled is not None:
        rule.is_enabled = data.is_enabled

    rule.updated_at = datetime.now(UTC).replace(tzinfo=None)
    mapping_set.version += 1
    mapping_set.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(
    db: AsyncSession,
    set_id: uuid.UUID,
    rule_id: uuid.UUID,
) -> None:
    mapping_set = await get_mapping_set(db, set_id)
    if not mapping_set:
        raise ValueError("ExportMappingSet nicht gefunden.")
    if mapping_set.status != "draft":
        raise ValueError("Regeln können nur aus Entwürfen gelöscht werden.")

    result = await db.execute(
        select(ExportMappingRule).where(
            ExportMappingRule.id == rule_id,
            ExportMappingRule.mapping_set_id == set_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise ValueError("ExportMappingRule nicht gefunden.")

    await db.delete(rule)
    mapping_set.version += 1
    mapping_set.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()


# ---------------------------------------------------------------------------
# Validation & Atomic Publication
# ---------------------------------------------------------------------------


def compile_mapping_set(mapping_set: ExportMappingSet) -> CompiledMappingSet:
    rules: list[MappingSpec] = []
    for r in sorted(mapping_set.rules, key=lambda x: x.sort_order):
        sk = (
            SourceKind(r.source_kind)
            if r.source_kind in SourceKind._value2member_map_
            else SourceKind.FIELD
        )
        rules.append(
            MappingSpec(
                rule_key=r.rule_key,
                source_kind=sk,
                source_config=dict(r.source_config or {}),
                target_key=r.target_key,
                settings=dict(r.settings or {}),
                sort_order=r.sort_order,
                is_enabled=r.is_enabled,
            )
        )
    return CompiledMappingSet(
        format_key=mapping_set.format_key,
        record_type=mapping_set.record_type,
        rules=rules,
        institution_config=dict(mapping_set.institution_config or {}),
    )


async def validate_mapping_set(
    db: AsyncSession,
    set_id: uuid.UUID,
) -> list[MappingDiagnostic]:
    from katalon.services import metadata_format_service

    mapping_set = await get_mapping_set(db, set_id)
    if not mapping_set:
        raise ValueError("ExportMappingSet nicht gefunden.")

    fmt = await metadata_format_service.get_format(mapping_set.format_key)
    if not fmt:
        return [
            MappingDiagnostic(
                code="unknown_format",
                message=f"Unbekanntes Format '{mapping_set.format_key}'.",
                level="error",
            )
        ]

    cms = compile_mapping_set(mapping_set)
    return fmt.validate_mapping(cms)


async def preview_mapping_set(
    db: AsyncSession,
    set_id: uuid.UUID,
    record_id: uuid.UUID,
) -> tuple[str, list[MappingDiagnostic]]:
    """Render one record through a mapping set's draft/published rules for live preview."""
    import xml.etree.ElementTree as ET

    from katalon.services import export_context_service, metadata_format_service

    mapping_set = await get_mapping_set(db, set_id)
    if not mapping_set:
        raise ValueError("ExportMappingSet nicht gefunden.")

    fmt = await metadata_format_service.get_format(mapping_set.format_key)
    if not fmt:
        raise ValueError(f"Unbekanntes Format '{mapping_set.format_key}'.")

    diagnostics = fmt.validate_mapping(compile_mapping_set(mapping_set))
    ctx = await export_context_service.build_export_context_from_db(
        db, mapping_set.record_type, record_id
    )
    element = fmt.render(ctx, compile_mapping_set(mapping_set))
    xml = ET.tostring(element, encoding="unicode")
    return xml, diagnostics


async def publish_mapping_set(
    db: AsyncSession,
    set_id: uuid.UUID,
    expected_version: int | None = None,
    user_id: uuid.UUID | None = None,
) -> ExportMappingSet:
    """Atomically publish a draft set, archiving any previously published set for this type/format."""
    mapping_set = await get_mapping_set(db, set_id)
    if not mapping_set:
        raise ValueError("ExportMappingSet nicht gefunden.")
    if mapping_set.status != "draft":
        raise ValueError("Nur Entwürfe (status='draft') können veröffentlicht werden.")
    if expected_version is not None and mapping_set.version != expected_version:
        raise OptimisticLockError(
            f"Konflikt: Aktuelle Version ist {mapping_set.version}, erwartet wurde {expected_version}."
        )

    # 1. Run validation: block publication if error diagnostics exist
    diagnostics = await validate_mapping_set(db, set_id)
    errors = [d for d in diagnostics if d.level == "error"]
    if errors:
        msg = "; ".join(f"[{e.code}] {e.message}" for e in errors)
        raise ValueError(f"Veröffentlichung fehlgeschlagen. Validierungsfehler: {msg}")

    now = datetime.now(UTC).replace(tzinfo=None)

    # 2. Archive any existing published set with matching (format_key, profile_id, record_type, target_subtype)
    q_existing = select(ExportMappingSet).where(
        ExportMappingSet.format_key == mapping_set.format_key,
        ExportMappingSet.profile_id == mapping_set.profile_id,
        ExportMappingSet.record_type == mapping_set.record_type,
        ExportMappingSet.status == "published",
    )
    if mapping_set.target_subtype:
        q_existing = q_existing.where(ExportMappingSet.target_subtype == mapping_set.target_subtype)
    else:
        q_existing = q_existing.where(ExportMappingSet.target_subtype.is_(None))

    result_existing = await db.execute(q_existing)
    for prev_set in result_existing.scalars().all():
        if prev_set.id != mapping_set.id:
            prev_set.status = "archived"
            prev_set.updated_at = now
            prev_set.version += 1
            log_archive = AuditLog(
                record_type="export_mapping_set",
                record_id=prev_set.id,
                user_id=user_id,
                action="archive",
                changed_fields={"status": "archived", "revision": prev_set.revision},
            )
            db.add(log_archive)

    # Flush archive updates first: the partial unique index on status='published'
    # is checked per-statement, not deferred to commit, so the previous published
    # row must be archived before this row transitions to published.
    await db.flush()

    # 3. Publish draft set
    mapping_set.status = "published"
    mapping_set.published_at = now
    mapping_set.updated_at = now
    mapping_set.version += 1

    log_publish = AuditLog(
        record_type="export_mapping_set",
        record_id=mapping_set.id,
        user_id=user_id,
        action="publish",
        changed_fields={"status": "published", "revision": mapping_set.revision},
    )
    db.add(log_publish)

    await db.commit()
    return await get_mapping_set(db, mapping_set.id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Value Extraction Helpers
# ---------------------------------------------------------------------------


def extract_values(src: dict[str, Any] | ExportRecordContext, field_name: str) -> list[str]:
    if isinstance(src, ExportRecordContext):
        raw = src.fields.get(field_name)
        if raw is None and field_name in {"idno", "title"}:
            raw = getattr(src.record, field_name, None)
        values = _flatten_value(raw)
        return [v for v in values if v]

    md = src.get("metadata", {}) or {}
    raw = md.get(field_name)
    if raw is None and field_name in {"idno", "title", "created_at", "updated_at"}:
        raw = src.get(field_name)
    values = _flatten_value(raw)
    return [v for v in values if v]

def _flatten_value(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_value(item))
        return out
    if isinstance(value, dict):
        for key in ("value", "label", "term", "name", "title", "idno"):
            if key not in value:
                continue
            nested = value[key]
            if isinstance(nested, dict):
                text = nested.get("de") or nested.get("en") or next(
                    (str(v) for v in nested.values() if v),
                    "",
                )
                return [text] if text else []
            return _flatten_value(nested)
        return []
    return [str(value)]
