# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, Query

from katalon.core.concurrency import check_version
from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.schemas import (
    ExportMappingRuleCreate,
    ExportMappingRuleRead,
    ExportMappingRuleUpdate,
    ExportMappingSetCreate,
    ExportMappingSetDetail,
    ExportMappingSetRead,
    ExportMappingSetUpdate,
    MappingPreviewRequest,
    MappingPreviewResult,
)
from katalon.integrations.metadata_format import MappingDiagnostic
from katalon.services import metadata_mapping_service
from katalon.services.metadata_mapping_service import OptimisticLockError

router = APIRouter(prefix="/export-mapping-sets", tags=["export-mapping-sets"])


def _require_admin(current_user: CurrentUser) -> None:
    if current_user.role not in {"admin", "superuser"}:
        raise HTTPException(
            status_code=403,
            detail="Nur Admins können Export-Mappings verwalten.",
        )


@router.get(
    "",
    response_model=list[ExportMappingSetDetail],
    summary="List export mapping sets filtered by record_type, format_key, or status",
)
async def list_export_mapping_sets(
    db: DBDep,
    record_type: str | None = Query(None),
    format_key: str | None = Query(None),
    status: str | None = Query(None),
) -> list[ExportMappingSetDetail]:
    sets = await metadata_mapping_service.list_mapping_sets(
        db,
        record_type=record_type,
        format_key=format_key,
        status=status,
    )
    return [ExportMappingSetDetail.model_validate(s) for s in sets]


@router.post(
    "",
    response_model=ExportMappingSetDetail,
    status_code=201,
    summary="Create a new draft export mapping set, optionally cloned from based_on_id",
)
async def create_export_mapping_set(
    data: ExportMappingSetCreate,
    db: DBDep,
    current_user: CurrentUser,
) -> ExportMappingSetDetail:
    _require_admin(current_user)
    mapping_set = await metadata_mapping_service.create_mapping_set(
        db,
        data,
        user_id=current_user.id,
    )
    return ExportMappingSetDetail.model_validate(mapping_set)


@router.get(
    "/{set_id}",
    response_model=ExportMappingSetDetail,
    summary="Get export mapping set detail with rules",
)
async def get_export_mapping_set(
    set_id: uuid.UUID,
    db: DBDep,
) -> ExportMappingSetDetail:
    mapping_set = await metadata_mapping_service.get_mapping_set(db, set_id)
    if not mapping_set:
        raise HTTPException(status_code=404, detail="Export-Mapping-Set nicht gefunden.")
    return ExportMappingSetDetail.model_validate(mapping_set)


@router.patch(
    "/{set_id}",
    response_model=ExportMappingSetRead,
    summary="Update draft export mapping set name or institution_config",
)
async def update_export_mapping_set(
    set_id: uuid.UUID,
    data: ExportMappingSetUpdate,
    db: DBDep,
    current_user: CurrentUser,
    if_match: int | None = Header(None, alias="If-Match"),
) -> ExportMappingSetRead:
    _require_admin(current_user)
    existing = await metadata_mapping_service.get_mapping_set(db, set_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Export-Mapping-Set nicht gefunden.")
    check_version(existing.version, if_match)
    try:
        updated = await metadata_mapping_service.update_mapping_set(
            db,
            set_id,
            data,
            expected_version=if_match,
            user_id=current_user.id,
        )
        return ExportMappingSetRead.model_validate(updated)
    except OptimisticLockError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "version_conflict", "current_version": existing.version},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{set_id}",
    status_code=204,
    summary="Delete draft or archived export mapping set",
)
async def delete_export_mapping_set(
    set_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
) -> None:
    _require_admin(current_user)
    try:
        await metadata_mapping_service.delete_mapping_set(
            db,
            set_id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{set_id}/rules",
    response_model=ExportMappingRuleRead,
    status_code=201,
    summary="Add a mapping rule to a draft mapping set",
)
async def create_mapping_rule(
    set_id: uuid.UUID,
    data: ExportMappingRuleCreate,
    db: DBDep,
    current_user: CurrentUser,
) -> ExportMappingRuleRead:
    _require_admin(current_user)
    try:
        rule = await metadata_mapping_service.create_rule(db, set_id, data)
        return ExportMappingRuleRead.model_validate(rule)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/{set_id}/rules/{rule_id}",
    response_model=ExportMappingRuleRead,
    summary="Update a mapping rule in a draft mapping set",
)
async def update_mapping_rule(
    set_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: ExportMappingRuleUpdate,
    db: DBDep,
    current_user: CurrentUser,
) -> ExportMappingRuleRead:
    _require_admin(current_user)
    try:
        rule = await metadata_mapping_service.update_rule(db, set_id, rule_id, data)
        return ExportMappingRuleRead.model_validate(rule)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{set_id}/rules/{rule_id}",
    status_code=204,
    summary="Delete a mapping rule from a draft mapping set",
)
async def delete_mapping_rule(
    set_id: uuid.UUID,
    rule_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
) -> None:
    _require_admin(current_user)
    try:
        await metadata_mapping_service.delete_rule(db, set_id, rule_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{set_id}/validate",
    response_model=list[MappingDiagnostic],
    summary="Validate all rules in a mapping set against its format capability profile",
)
async def validate_mapping_set_endpoint(
    set_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
) -> list[MappingDiagnostic]:
    _require_admin(current_user)
    try:
        return await metadata_mapping_service.validate_mapping_set(db, set_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{set_id}/preview",
    response_model=MappingPreviewResult,
    summary="Render one record through a mapping set for live preview",
)
async def preview_mapping_set_endpoint(
    set_id: uuid.UUID,
    body: MappingPreviewRequest,
    db: DBDep,
    current_user: CurrentUser,
) -> MappingPreviewResult:
    _require_admin(current_user)
    try:
        xml, diagnostics = await metadata_mapping_service.preview_mapping_set(
            db, set_id, body.record_id
        )
        return MappingPreviewResult(xml=xml, diagnostics=diagnostics)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{set_id}/publish",
    response_model=ExportMappingSetRead,
    summary="Atomically publish a draft mapping set (archiving previously published set)",
)
async def publish_mapping_set_endpoint(
    set_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
    if_match: int | None = Header(None, alias="If-Match"),
) -> ExportMappingSetRead:
    _require_admin(current_user)
    existing = await metadata_mapping_service.get_mapping_set(db, set_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Export-Mapping-Set nicht gefunden.")
    check_version(existing.version, if_match)
    try:
        published = await metadata_mapping_service.publish_mapping_set(
            db,
            set_id,
            expected_version=if_match,
            user_id=current_user.id,
        )
        return ExportMappingSetRead.model_validate(published)
    except OptimisticLockError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "version_conflict", "current_version": existing.version},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
