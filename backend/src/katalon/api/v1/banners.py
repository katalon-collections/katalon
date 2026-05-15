from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import Banner

router = APIRouter(prefix="/banners", tags=["banners"])

VALID_COLORS = {"blue", "yellow", "red", "green"}


class BannerCreate(BaseModel):
    message: str
    color: str = "blue"
    show_admin: bool = True
    show_portal: bool = True
    is_active: bool = True
    expires_at: datetime | None = None


class BannerUpdate(BaseModel):
    message: str | None = None
    color: str | None = None
    show_admin: bool | None = None
    show_portal: bool | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None


class BannerRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    message: str
    color: str
    show_admin: bool
    show_portal: bool
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _active_filter(q: object, *, surface: str) -> object:
    """Return banners that are active, not expired, and visible on `surface`."""
    now = datetime.utcnow()
    from sqlalchemy import or_

    q = q.where(Banner.is_active.is_(True))
    q = q.where(or_(Banner.expires_at.is_(None), Banner.expires_at > now))
    if surface == "admin":
        q = q.where(Banner.show_admin.is_(True))
    elif surface == "portal":
        q = q.where(Banner.show_portal.is_(True))
    return q


# ---------------------------------------------------------------------------
# Public endpoints (no auth required — frontends poll these)
# ---------------------------------------------------------------------------


@router.get("/active/admin", response_model=list[BannerRead])
async def active_admin_banners(db: DBDep) -> list[Banner]:
    """Return active banners for the admin surface."""
    q = select(Banner).order_by(Banner.created_at.desc())
    q = _active_filter(q, surface="admin")
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/active/portal", response_model=list[BannerRead])
async def active_portal_banners(db: DBDep) -> list[Banner]:
    """Return active banners for the portal surface."""
    q = select(Banner).order_by(Banner.created_at.desc())
    q = _active_filter(q, surface="portal")
    result = await db.execute(q)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Admin CRUD (requires auth)
# ---------------------------------------------------------------------------


@router.get("", response_model=list[BannerRead])
async def list_banners(db: DBDep, _: CurrentUser) -> list[Banner]:
    result = await db.execute(select(Banner).order_by(Banner.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=BannerRead, status_code=201)
async def create_banner(body: BannerCreate, db: DBDep, _: CurrentUser) -> Banner:
    if body.color not in VALID_COLORS:
        raise HTTPException(status_code=422, detail=f"Ungültige Farbe. Erlaubt: {', '.join(VALID_COLORS)}")
    banner = Banner(**body.model_dump())
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return banner


@router.put("/{banner_id}", response_model=BannerRead)
async def update_banner(banner_id: uuid.UUID, body: BannerUpdate, db: DBDep, _: CurrentUser) -> Banner:
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner nicht gefunden")
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "color" and value not in VALID_COLORS:
            raise HTTPException(status_code=422, detail=f"Ungültige Farbe. Erlaubt: {', '.join(VALID_COLORS)}")
        setattr(banner, field, value)
    await db.commit()
    await db.refresh(banner)
    return banner


@router.delete("/{banner_id}", status_code=204)
async def delete_banner(banner_id: uuid.UUID, db: DBDep, _: CurrentUser) -> None:
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner nicht gefunden")
    await db.delete(banner)
    await db.commit()
