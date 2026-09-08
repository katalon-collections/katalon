# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import FieldDefinition, MetadataMapping
from katalon.core.schemas import (
    FormatOut,
    MetadataMappingCreate,
    MetadataMappingRead,
    MetadataMappingUpsert,
)
from katalon.services import metadata_format_service
from katalon.services.metadata_mapping_service import get_mappings, validate_mapping_target

router = APIRouter(prefix="/metadata-mappings", tags=["metadata-mappings"])


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role not in {"admin", "superuser"}:
        raise HTTPException(
            status_code=403,
            detail="Nur Admins können Metadaten-Mappings verwalten.",
        )




@router.get(
    "/formats",
    response_model=list[FormatOut],
    summary="List registered export formats and their mappable targets",
)
async def list_formats() -> list[FormatOut]:
    formats = await metadata_format_service.list_formats()
    return [
        FormatOut(
            key=f.key,
            label=f.label,
            targets=sorted(f.targets),
            capabilities=f.capabilities(),
        )
        for f in formats
    ]


@router.get(
    "",
    response_model=list[MetadataMappingRead],
    summary="List metadata mappings",
)
async def list_metadata_mappings(
    db: DBDep,
    format_key: str | None = Query(None),
    field_definition_id: uuid.UUID | None = Query(None),
) -> list[MetadataMapping]:
    return await get_mappings(
        db,
        format_key=format_key,
        field_definition_id=field_definition_id,
    )


@router.post(
    "",
    response_model=MetadataMappingRead,
    status_code=201,
    summary="Create a metadata mapping",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid mapping target"},
        404: {"description": "Field definition not found"},
    },
)
async def create_metadata_mapping(
    data: MetadataMappingCreate,
    db: DBDep,
    current_user: CurrentUser,
) -> MetadataMapping:
    _require_admin(current_user)
    try:
        await validate_mapping_target(data.format_key, data.target_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    field = await db.get(FieldDefinition, data.field_definition_id)
    if not field or field.is_deleted:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden.")

    mapping = MetadataMapping(**data.model_dump())
    db.add(mapping)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(mapping)
    return mapping


@router.put(
    "/field/{field_definition_id}/{format_key}",
    response_model=MetadataMappingRead | None,
    summary="Create, update, or clear a field-to-format mapping",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Field definition not found"},
        422: {"description": "Invalid mapping target"},
    },
)
async def set_field_format_mapping(
    field_definition_id: uuid.UUID,
    format_key: str,
    data: MetadataMappingUpsert,
    db: DBDep,
    current_user: CurrentUser,
) -> MetadataMapping | None:
    _require_admin(current_user)
    field = await db.get(FieldDefinition, field_definition_id)
    if not field or field.is_deleted:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden.")

    existing_result = await db.execute(
        select(MetadataMapping).where(
            MetadataMapping.field_definition_id == field_definition_id,
            MetadataMapping.format_key == format_key,
        )
    )
    existing = list(existing_result.scalars().all())

    if data.target_path is None or not data.target_path.strip():
        for mapping in existing:
            await db.delete(mapping)
        await db.commit()
        return None

    target_path = data.target_path.strip()
    try:
        await validate_mapping_target(format_key, target_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    mapping = existing[0] if existing else MetadataMapping(
        field_definition_id=field_definition_id,
        format_key=format_key,
        target_path=target_path,
    )
    mapping.target_path = target_path
    mapping.settings = data.settings
    mapping.sort_order = data.sort_order
    mapping.is_enabled = data.is_enabled
    db.add(mapping)
    for extra in existing[1:]:
        await db.delete(extra)
    await db.commit()
    await db.refresh(mapping)
    return mapping


@router.delete(
    "/{mapping_id}",
    status_code=204,
    summary="Delete a metadata mapping",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Metadata mapping not found"},
    },
)
async def delete_metadata_mapping(
    mapping_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
) -> None:
    _require_admin(current_user)
    mapping = await db.get(MetadataMapping, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Metadaten-Mapping nicht gefunden.")
    await db.delete(mapping)
    await db.commit()
