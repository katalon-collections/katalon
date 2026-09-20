# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from katalon.core.models import (
    AuditLog,
    ExportMappingRule,
    ExportMappingSet,
    FieldDefinition,
    PortalConfig,
    RecordSubtype,
)
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
            institution_config=dict(mapping_set.institution_config or {}),
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

    institution_config = dict(data.institution_config or {})
    if (
        data.format_key == "lido"
        and data.record_type == "object"
        and data.based_on_id is None
        and not institution_config.get("institution_name")
    ):
        portal_result = await db.execute(
            select(PortalConfig).where(PortalConfig.key == "default")
        )
        portal_config = portal_result.scalar_one_or_none()
        site_title = portal_config.site_title if portal_config else {}
        institution_name = (
            site_title.get("de")
            or site_title.get("en")
            or next((title for title in site_title.values() if title), "")
        )
        if institution_name.strip():
            institution_config["institution_name"] = institution_name.strip()

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
        institution_config=institution_config,
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

    if (
        data.format_key == "lido"
        and data.record_type == "object"
        and data.based_on_id is None
    ):
        db.add(
            ExportMappingRule(
                mapping_set_id=new_set.id,
                source_kind=SourceKind.FIELD.value,
                source_config={"field_name": "label"},
                target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
                settings={},
                sort_order=0,
                is_enabled=True,
            )
        )
    elif (
        data.format_key == "mets_mods"
        and data.record_type == "object"
        and data.based_on_id is None
    ):
        db.add(
            ExportMappingRule(
                mapping_set_id=new_set.id,
                source_kind=SourceKind.FIELD.value,
                source_config={"field_name": "label"},
                target_key="mods:titleInfo/mods:title",
                settings={},
                sort_order=0,
                is_enabled=True,
            )
        )
        db.add(
            ExportMappingRule(
                mapping_set_id=new_set.id,
                source_kind=SourceKind.MEDIA.value,
                source_config={"property": "license_uri"},
                target_key="mods:accessCondition",
                settings={},
                sort_order=1,
                is_enabled=True,
            )
        )

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




async def _validate_lido_subtype_authorities(
    db: AsyncSession,
    mapping_set: ExportMappingSet,
    compiled: CompiledMappingSet,
) -> list[MappingDiagnostic]:
    work_type_target = "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"
    uses_subtype_authorities = any(
        rule.is_enabled
        and rule.target_key == work_type_target
        and rule.source_kind == SourceKind.RECORD
        for rule in compiled.rules
    )
    if mapping_set.format_key != "lido" or mapping_set.record_type != "object" or not uses_subtype_authorities:
        return []

    result = await db.execute(
        select(RecordSubtype).where(RecordSubtype.primary_type == "object")
    )
    missing = [
        (subtype.label or {}).get("de")
        or (subtype.label or {}).get("en")
        or subtype.name
        for subtype in result.scalars().all()
        if not subtype.concept_id and not subtype.concept_uri
    ]
    if not missing:
        return []

    return [
        MappingDiagnostic(
            code="subtype_authority_missing",
            message=f"Subtypen ohne Normdaten: {', '.join(missing)}.",
            target_key=work_type_target,
        )
    ]


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
    diagnostics = fmt.validate_mapping(cms)
    diagnostics.extend(await _validate_lido_subtype_authorities(db, mapping_set, cms))
    return diagnostics


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

    cms = compile_mapping_set(mapping_set)
    diagnostics = fmt.validate_mapping(cms)
    ctx = await export_context_service.build_export_context_from_db(
        db, mapping_set.record_type, record_id
    )
    element = fmt.render(ctx, cms)
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
# YAML Export & Import
# ---------------------------------------------------------------------------


async def export_mapping_set_to_yaml(db: AsyncSession, set_id: uuid.UUID) -> tuple[str, str]:
    """Serialize an ExportMappingSet and its rules to portable YAML."""
    result = await db.execute(
        select(ExportMappingSet)
        .options(
            selectinload(ExportMappingSet.rules).selectinload(ExportMappingRule.field_definition)
        )
        .where(ExportMappingSet.id == set_id)
    )
    mapping_set = result.scalar_one_or_none()
    if not mapping_set:
        raise ValueError("ExportMappingSet nicht gefunden.")

    rules_data: list[dict[str, Any]] = []
    for r in sorted(mapping_set.rules, key=lambda x: x.sort_order):
        field_name = (
            r.field_definition.name
            if r.field_definition
            else (r.source_config or {}).get("field_name")
        )
        rule_dict: dict[str, Any] = {
            "rule_key": str(r.rule_key),
            "source_kind": r.source_kind,
            "target_key": r.target_key,
            "sort_order": r.sort_order,
            "is_enabled": r.is_enabled,
        }
        if field_name:
            rule_dict["field_name"] = field_name
        if r.source_config:
            rule_dict["source_config"] = dict(r.source_config)
        if r.settings:
            rule_dict["settings"] = dict(r.settings)
        rules_data.append(rule_dict)

    data: dict[str, Any] = {
        "schema_version": "1.0",
        "format_key": mapping_set.format_key,
        "profile_id": mapping_set.profile_id,
        "profile_version": mapping_set.profile_version,
        "record_type": mapping_set.record_type,
        "name": mapping_set.name,
    }
    if mapping_set.target_subtype:
        data["target_subtype"] = mapping_set.target_subtype
    if mapping_set.institution_config:
        data["institution_config"] = dict(mapping_set.institution_config)
    data["rules"] = rules_data

    yaml_content = yaml.dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    subtype_suffix = f"-{mapping_set.target_subtype}" if mapping_set.target_subtype else ""
    filename = (
        f"export-mapping-{mapping_set.format_key}-{mapping_set.record_type}"
        f"{subtype_suffix}-rev{mapping_set.revision}.yaml"
    )
    return yaml_content, filename


async def import_mapping_set_from_yaml(
    db: AsyncSession,
    yaml_content: str,
    *,
    user_id: uuid.UUID | None = None,
    target_set_id: uuid.UUID | None = None,
    dry_run: bool = False,
) -> tuple[ExportMappingSet, list[str]]:
    """Import an ExportMappingSet and its rules from YAML.

    Resolves field names to field_definition_id on the current target type.
    If target_set_id is given, overwrites rules in that draft set.
    Otherwise, creates a new draft set with the next revision number.
    """
    try:
        data = yaml.safe_load(yaml_content)
    except Exception as exc:
        raise ValueError(f"YAML konnte nicht geparst werden: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Ungültiges YAML-Format: Wurzelknoten muss ein Mapping/Dictionary sein.")

    format_key = data.get("format_key")
    record_type = data.get("record_type")
    if not format_key or not record_type:
        raise ValueError("YAML muss 'format_key' und 'record_type' enthalten.")

    target_subtype = data.get("target_subtype")
    now = datetime.now(UTC).replace(tzinfo=None)

    if target_set_id:
        target_set = await get_mapping_set(db, target_set_id)
        if not target_set:
            raise ValueError("Ziel-ExportMappingSet nicht gefunden.")
        if target_set.status != "draft":
            raise ValueError("Nur Entwürfe (status='draft') können durch Import überschrieben werden.")
        if target_set.format_key != format_key or target_set.record_type != record_type:
            raise ValueError(
                f"Format ({format_key}) oder Datensatztyp ({record_type}) der Datei stimmen nicht "
                f"mit dem Ziel-Set ({target_set.format_key}/{target_set.record_type}) überein."
            )
        if data.get("name"):
            target_set.name = str(data["name"])
        if "institution_config" in data and isinstance(data["institution_config"], dict):
            target_set.institution_config = {
                **dict(target_set.institution_config or {}),
                **data["institution_config"],
            }
        for existing_rule in list(target_set.rules):
            await db.delete(existing_rule)
        await db.flush()
    else:
        q_rev = select(ExportMappingSet.revision).where(
            ExportMappingSet.format_key == format_key,
            ExportMappingSet.record_type == record_type,
        )
        if target_subtype:
            q_rev = q_rev.where(ExportMappingSet.target_subtype == target_subtype)
        else:
            q_rev = q_rev.where(ExportMappingSet.target_subtype.is_(None))
        revs = (await db.execute(q_rev)).scalars().all()
        revision = max(revs) + 1 if revs else 1

        q_pub = select(ExportMappingSet.id).where(
            ExportMappingSet.format_key == format_key,
            ExportMappingSet.record_type == record_type,
            ExportMappingSet.status == "published",
        )
        if target_subtype:
            q_pub = q_pub.where(ExportMappingSet.target_subtype == target_subtype)
        else:
            q_pub = q_pub.where(ExportMappingSet.target_subtype.is_(None))
        based_on_id = (await db.execute(q_pub)).scalar_one_or_none()

        target_set = ExportMappingSet(
            format_key=format_key,
            profile_id=str(data.get("profile_id", f"{format_key}-default")),
            profile_version=str(data.get("profile_version", "1.0")),
            record_type=record_type,
            target_subtype=target_subtype,
            name=str(data.get("name") or f"{format_key.upper()} {record_type.capitalize()} Mapping"),
            status="draft",
            revision=revision,
            based_on_id=based_on_id,
            institution_config=dict(data.get("institution_config") or {}),
            version=1,
            created_by=user_id,
        )
        db.add(target_set)
        await db.flush()

    # Load field definitions for this record_type to resolve field names to IDs
    fields_res = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == target_set.record_type,
            FieldDefinition.is_deleted.is_(False),
        )
    )
    field_by_name = {f.name: f for f in fields_res.scalars().all()}

    warnings: list[str] = []
    raw_rules = data.get("rules") or []
    if not isinstance(raw_rules, list):
        raise ValueError("Das Attribut 'rules' muss eine Liste sein.")

    added_rules_count = 0
    for idx, r in enumerate(raw_rules):
        if not isinstance(r, dict):
            continue
        target_key = r.get("target_key")
        if not target_key:
            warnings.append(f"Regel #{idx + 1} ohne 'target_key' übersprungen.")
            continue

        source_kind = str(r.get("source_kind", "field"))
        source_cfg = dict(r.get("source_config") or {})
        settings = dict(r.get("settings") or {})
        sort_order = int(r.get("sort_order", idx * 10))
        is_enabled = bool(r.get("is_enabled", True))

        raw_key = r.get("rule_key")
        rule_key = None
        if raw_key:
            try:
                rule_key = uuid.UUID(str(raw_key))
            except (ValueError, TypeError):
                rule_key = None
        if rule_key is None:
            rule_key = uuid.uuid4()

        field_name = r.get("field_name") or source_cfg.get("field_name")
        field_def_id = None
        if source_kind == "field" or field_name:
            if field_name:
                fd = field_by_name.get(field_name)
                if fd:
                    field_def_id = fd.id
                    source_cfg["field_name"] = fd.name
                    source_cfg["field_type"] = fd.field_type
                else:
                    warnings.append(
                        f"Feld '{field_name}' existiert nicht für Typ '{target_set.record_type}'. "
                        f"Regel für '{target_key}' wurde ohne Feldzuordnung importiert."
                    )
            else:
                warnings.append(
                    f"Regel für '{target_key}' hat Quellentyp 'field', aber keinen Feldnamen angegeben."
                )

        new_rule = ExportMappingRule(
            rule_key=rule_key,
            mapping_set_id=target_set.id,
            source_kind=source_kind,
            field_definition_id=field_def_id,
            source_config=source_cfg,
            target_key=target_key,
            settings=settings,
            sort_order=sort_order,
            is_enabled=is_enabled,
        )
        db.add(new_rule)
        added_rules_count += 1

    target_set.version += 1
    target_set.updated_at = now
    await db.flush()

    if dry_run:
        await db.rollback()
        return target_set, warnings, added_rules_count

    log = AuditLog(
        record_type="export_mapping_set",
        record_id=target_set.id,
        user_id=user_id,
        action="import_yaml",
        changed_fields={
            "name": target_set.name,
            "format_key": target_set.format_key,
            "record_type": target_set.record_type,
            "revision": target_set.revision,
            "rules_count": added_rules_count,
            "warnings": warnings,
        },
    )
    db.add(log)
    await db.commit()

    refreshed = await get_mapping_set(db, target_set.id)
    return refreshed or target_set, warnings, added_rules_count


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
