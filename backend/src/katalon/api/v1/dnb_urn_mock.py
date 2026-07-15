from __future__ import annotations

import random
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/dnb-urn-mock", tags=["dnb-urn-mock"])

_registered: dict[str, list[dict[str, str | int]]] = {}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RegisterUrlIn(BaseModel):
    url: HttpUrl
    priority: int = 10


class RegisterUrnIn(BaseModel):
    urn: str
    urls: list[RegisterUrlIn]


@router.get(
    "/namespaces/name/{name}/urn-suggestion",
    summary="Suggest a mock URN for a namespace",
)
async def urn_suggestion(name: str) -> dict:
    suffix = random.randint(1_000_000_000, 9_999_999_999)
    return {
        "suggestedUrn": f"{name}-{suffix}",
        "namespace": f"/dnb-urn-mock/namespaces/name/{name}",
        "self": f"/dnb-urn-mock/namespaces/name/{name}/urn-suggestion",
    }


@router.post(
    "/urns",
    status_code=201,
    summary="Register a mock URN with its target URLs",
    responses={400: {"description": "At least one URL is required"}},
)
async def register_urn(data: RegisterUrnIn) -> dict:
    if not data.urls:
        raise HTTPException(status_code=400, detail="Mindestens eine URL ist erforderlich.")
    now = _now_iso()
    _registered[data.urn] = [{"url": str(u.url), "priority": u.priority} for u in data.urls]
    return {
        "urn": data.urn,
        "created": now,
        "lastModified": now,
        "urls": f"/dnb-urn-mock/urns/urn/{data.urn}/urls",
        "myUrls": f"/dnb-urn-mock/urns/urn/{data.urn}/my-urls",
        "self": f"/dnb-urn-mock/urns/urn/{data.urn}",
    }


@router.get(
    "/urns/urn/{urn}/my-urls",
    summary="List registered URLs for a mock URN",
    responses={404: {"description": "URN not found"}},
)
async def get_my_urls(urn: str) -> dict:
    items = _registered.get(urn)
    if not items:
        raise HTTPException(status_code=404, detail="URN nicht gefunden.")
    now = _now_iso()
    return {
        "totalItems": len(items),
        "items": [
            {
                "url": item["url"],
                "priority": item["priority"],
                "created": now,
                "lastModified": now,
            }
            for item in items
        ],
        "self": f"/dnb-urn-mock/urns/urn/{urn}/my-urls",
    }
