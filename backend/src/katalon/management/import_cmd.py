# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""CSV/XML import helpers for the management CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.api.v1.importer import VALID_TYPES
from katalon.core.models import FieldDefinition, RecordSubtype
from katalon.database import AsyncSessionLocal
from katalon.services import importer_service
from katalon.services.importer import parse_csv
from katalon.services.importer.formats.xml_format import XmlFormat


async def _load_field_definitions(
    db: AsyncSession, record_type: str
) -> dict[str, FieldDefinition]:
    """Load active field definitions for the given record type."""
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == record_type,
            FieldDefinition.is_deleted.is_(False),
        )
    )
    return {f.name: f for f in result.scalars().all()}


def _load_mapping(path: str) -> dict[str, Any]:
    """Load a JSON mapping file.

    Expected format:
        {"source_column": {"target": "field_name", "transforms": [...]}}
    Or an exported profile envelope:
        {"version": 1, "record_type": "...", "mapping": {...}}
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise click.ClickException("Mapping file must contain a JSON object.")
    if "mapping" in data and isinstance(data["mapping"], dict):
        data = data["mapping"]
    return data

def _normalize_mapping(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize mapping values to the shape the importer service expects."""
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            normalized[key] = {"target": value, "transforms": []}
        elif isinstance(value, dict):
            target = value.get("target")
            if not target:
                raise click.ClickException(f"Mapping entry '{key}' is missing 'target'.")
            transforms = value.get("transforms", [])
            normalized[key] = {"target": target, "transforms": transforms}
        else:
            raise click.ClickException(
                f"Mapping entry '{key}' must be a string or an object."
            )
    return normalized


async def _validate_subtype(db: AsyncSession, record_type: str, subtype: str | None) -> None:
    """Ensure the requested subtype exists for the record type."""
    if not subtype:
        return
    result = await db.execute(
        select(RecordSubtype).where(
            RecordSubtype.primary_type == record_type,
            RecordSubtype.name == subtype,
        )
    )
    if result.scalar_one_or_none() is None:
        raise click.ClickException(f"Invalid subtype '{subtype}' for {record_type}.")


async def _run_import(
    record_type: str,
    rows: list[dict[str, str]],
    mapping: dict[str, Any],
    subtype: str | None,
    idno_strategy: str,
    upsert_strategy: str,
    auto_publish: bool,
    media_selector: str | None,
    dry_run: bool,
) -> None:
    """Shared import logic for CSV and XML."""
    if record_type not in VALID_TYPES:
        raise click.ClickException(
            f"Invalid record type '{record_type}'. Must be one of: {', '.join(sorted(VALID_TYPES))}."
        )
    if media_selector and record_type != "object":
        raise click.ClickException("Media selector is only supported for objects.")

    async with AsyncSessionLocal() as db:
        await _validate_subtype(db, record_type, subtype)
        field_defs = await _load_field_definitions(db, record_type)

    norm_mapping = _normalize_mapping(mapping)

    if dry_run:
        dry_result = importer_service.dry_run(rows, norm_mapping, field_defs)
        click.echo(json.dumps(dry_result, indent=2, ensure_ascii=False))
        return

    from katalon.workers.import_tasks import import_records_task

    result = import_records_task.run(
        record_type,
        rows,
        norm_mapping,
        idno_strategy=idno_strategy,
        upsert_strategy=upsert_strategy,
        auto_publish=auto_publish,
        user_id=None,
        subtype=subtype,
        fields_to_create=None,
        media_selector=media_selector,
    )
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


def import_csv(
    file: str,
    record_type: str,
    mapping_path: str,
    subtype: str | None,
    idno_strategy: str,
    upsert_strategy: str,
    auto_publish: bool,
    media_selector: str | None,
    dry_run: bool,
) -> None:
    """Import records from a CSV file."""
    content = Path(file).read_bytes()
    headers, rows = parse_csv(content)
    if not rows:
        raise click.ClickException("CSV file contains no rows.")
    click.echo(f"Loaded {len(rows)} rows with columns: {', '.join(headers)}")

    mapping = _load_mapping(mapping_path)
    import asyncio

    asyncio.run(
        _run_import(
            record_type=record_type,
            rows=rows,
            mapping=mapping,
            subtype=subtype,
            idno_strategy=idno_strategy,
            upsert_strategy=upsert_strategy,
            auto_publish=auto_publish,
            media_selector=media_selector,
            dry_run=dry_run,
        )
    )


def import_xml(
    file: str,
    record_type: str,
    mapping_path: str,
    record_xpath: str,
    subtype: str | None,
    idno_strategy: str,
    upsert_strategy: str,
    auto_publish: bool,
    media_selector: str | None,
    dry_run: bool,
) -> None:
    """Import records from an XML file."""
    content = Path(file).read_bytes()
    fmt = XmlFormat()
    if not fmt.sniff(content, Path(file).name):
        raise click.ClickException("File does not look like XML.")
    rows = list(fmt.parse_flat(content, record_xpath=record_xpath))
    if not rows:
        raise click.ClickException("No records found for the given record-xpath.")
    click.echo(f"Loaded {len(rows)} records from XML.")

    mapping = _load_mapping(mapping_path)
    import asyncio

    asyncio.run(
        _run_import(
            record_type=record_type,
            rows=rows,
            mapping=mapping,
            subtype=subtype,
            idno_strategy=idno_strategy,
            upsert_strategy=upsert_strategy,
            auto_publish=auto_publish,
            media_selector=media_selector,
            dry_run=dry_run,
        )
    )
