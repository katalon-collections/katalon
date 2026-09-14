# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from katalon.config import settings
from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.limiter import limiter
from katalon.core.models import AuthoritySource as AuthoritySourceModel
from katalon.services import authority_service

router = APIRouter(prefix="/authorities", tags=["authorities"])


class SourceOut(BaseModel):
    id: str
    label: str
    is_enabled: bool


class SourceUpdate(BaseModel):
    is_enabled: bool


class HitOut(BaseModel):
    source: str
    external_id: str
    label: str
    description: str
    extra: dict[str, Any]


@router.get(
    "/",
    response_model=list[SourceOut],
    summary="List registered authority sources",
)
async def list_sources(db: DBDep, _: CurrentUser) -> list[SourceOut]:
    result = await db.execute(select(AuthoritySourceModel))
    db_by_id = {s.id: s for s in result.scalars().all()}
    return [
        SourceOut(
            id=sid,
            label=db_by_id[sid].label if sid in db_by_id else authority_service.default_label(sid),
            is_enabled=db_by_id[sid].is_enabled if sid in db_by_id else True,
        )
        for sid in authority_service.list_sources()
    ]


@router.patch(
    "/{source_id}",
    response_model=SourceOut,
    summary="Enable or disable an authority source",
    dependencies=[require_role("admin")],
)
async def update_source(source_id: str, body: SourceUpdate, db: DBDep) -> SourceOut:
    if source_id not in authority_service.list_sources():
        raise HTTPException(status_code=404, detail=f"Unbekannte Authority-Quelle: {source_id}")
    row = await db.get(AuthoritySourceModel, source_id)
    if row is None:
        row = AuthoritySourceModel(
            id=source_id,
            label=authority_service.default_label(source_id),
            adapter_class=authority_service.default_adapter_class(source_id) or "",
            config={},
        )
        db.add(row)
    row.is_enabled = body.is_enabled
    await db.commit()
    authority_service.invalidate_cache()
    return SourceOut(id=row.id, label=row.label, is_enabled=row.is_enabled)


@router.get(
    "/search",
    response_model=list[HitOut],
    summary="Search an external authority source",
    responses={404: {"description": "Unknown authority source"}},
)
@limiter.limit(lambda: settings.rate_limit_authority_proxy)
async def search(
    request: Request,
    source: Annotated[str, Query(description="Adapter ID, e.g. gnd or geonames")],
    q: Annotated[str, Query(description="Search query")],
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[HitOut]:
    try:
        results = await authority_service.search(source, q, limit)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Verbindung zu Authority-Quelle '{source}' fehlgeschlagen: {e}") from e
    if results is None:
        raise HTTPException(status_code=404, detail=f"Unbekannte oder deaktivierte Authority-Quelle: {source}")
    return [HitOut(**r.__dict__) for r in results]


@router.get(
    "/fetch",
    response_model=HitOut,
    summary="Fetch a single record from an external authority source",
    responses={404: {"description": "Record not found"}},
)
@limiter.limit(lambda: settings.rate_limit_authority_proxy)
async def fetch(
    request: Request,
    source: Annotated[str, Query()],
    id: Annotated[str, Query(description="External ID to fetch")],
    _: CurrentUser,
) -> HitOut:
    try:
        hit = await authority_service.fetch(source, id)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Verbindung zu Authority-Quelle '{source}' fehlgeschlagen: {e}") from e
    if hit is None:
        raise HTTPException(status_code=404, detail="Datensatz nicht gefunden")
    return HitOut(**hit.__dict__)
