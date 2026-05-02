from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from katalon.services import authority_service

router = APIRouter(prefix="/authority", tags=["authority"])


class HitOut(BaseModel):
    source: str
    external_id: str
    label: str
    description: str
    extra: dict


@router.get("/sources")
async def list_sources() -> list[str]:
    return authority_service.list_sources()


@router.get("/search", response_model=list[HitOut])
async def search(
    source: Annotated[str, Query(description="Adapter ID, e.g. gnd or geonames")],
    q: Annotated[str, Query(description="Search query")],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[HitOut]:
    results = await authority_service.search(source, q, limit)
    if results is None:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source}")
    return [HitOut(**r.__dict__) for r in results]


@router.get("/fetch", response_model=HitOut)
async def fetch(
    source: Annotated[str, Query()],
    id: Annotated[str, Query(description="External ID to fetch")],
) -> HitOut:
    hit = await authority_service.fetch(source, id)
    if hit is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return HitOut(**hit.__dict__)
