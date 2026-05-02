from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import AuthoritySource as AuthoritySourceModel
from katalon.services import authority_service

router = APIRouter(prefix="/authorities", tags=["authorities"])


class SourceOut(BaseModel):
    id: str
    label: str
    is_enabled: bool


class HitOut(BaseModel):
    source: str
    external_id: str
    label: str
    description: str
    extra: dict


@router.get("/", response_model=list[SourceOut])
async def list_sources(db: DBDep, _: CurrentUser) -> list[SourceOut]:
    result = await db.execute(select(AuthoritySourceModel))
    sources = result.scalars().all()
    if not sources:
        # Return builtins if DB has no entries yet
        return [
            SourceOut(id=sid, label=sid.upper(), is_enabled=True)
            for sid in authority_service.list_sources()
        ]
    return [SourceOut(id=s.id, label=s.label, is_enabled=s.is_enabled) for s in sources]


@router.get("/search", response_model=list[HitOut])
async def search(
    source: Annotated[str, Query(description="Adapter ID, e.g. gnd or geonames")],
    q: Annotated[str, Query(description="Search query")],
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[HitOut]:
    results = await authority_service.search(source, q, limit)
    if results is None:
        raise HTTPException(status_code=404, detail=f"Unbekannte Authority-Quelle: {source}")
    return [HitOut(**r.__dict__) for r in results]


@router.get("/fetch", response_model=HitOut)
async def fetch(
    source: Annotated[str, Query()],
    id: Annotated[str, Query(description="External ID to fetch")],
    _: CurrentUser,
) -> HitOut:
    hit = await authority_service.fetch(source, id)
    if hit is None:
        raise HTTPException(status_code=404, detail="Datensatz nicht gefunden")
    return HitOut(**hit.__dict__)
