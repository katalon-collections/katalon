from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter
from sqlalchemy import select

from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import PortalConfig

router = APIRouter(prefix="/portal", tags=["portal"])

_DEFAULTS = {
    "site_title": "Katalon",
    "site_subtitle": "",
    "hero_text": "",
    "featured_object_ids": [],
    "accent_color": "#1e3a8a",
    "logo_url": "",
    "facet_fields": [],
}


class PortalConfigRead(BaseModel):
    site_title: str
    site_subtitle: str
    hero_text: str
    featured_object_ids: list[str]
    facet_fields: list[str]
    accent_color: str
    logo_url: str

    class Config:
        from_attributes = True


class PortalConfigUpdate(BaseModel):
    site_title: str | None = None
    site_subtitle: str | None = None
    hero_text: str | None = None
    featured_object_ids: list[str] | None = None
    facet_fields: list[str] | None = None
    accent_color: str | None = None
    logo_url: str | None = None


async def _get_or_create(db: DBDep) -> PortalConfig:
    result = await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
    config = result.scalar_one_or_none()
    if config is None:
        config = PortalConfig(key="default")
        db.add(config)
        await db.flush()
    return config


@router.get("/config", response_model=PortalConfigRead)
async def get_portal_config(db: DBDep) -> PortalConfig:
    return await _get_or_create(db)


@router.put("/config", response_model=PortalConfigRead)
async def update_portal_config(
    data: PortalConfigUpdate, db: DBDep, _=require_role("admin")
) -> PortalConfig:
    config = await _get_or_create(db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    await db.flush()
    return config
