from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import StaticPage

_SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

router = APIRouter(prefix="/pages", tags=["pages"])


class PageCreate(BaseModel):
    slug: str
    title: dict = {}
    content: dict = {}
    is_published: bool = False
    sort_order: int = 0

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError('Slug muss URL-sicher sein (nur Kleinbuchstaben, Zahlen, Bindestriche)')
        return v


class PageUpdate(BaseModel):
    title: dict | None = None
    content: dict | None = None
    is_published: bool | None = None
    sort_order: int | None = None


class PageRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    slug: str
    title: dict
    content: dict
    is_published: bool
    sort_order: int


@router.get("", response_model=list[PageRead])
async def list_pages(db: DBDep) -> list[StaticPage]:
    result = await db.execute(
        select(StaticPage).where(StaticPage.is_published.is_(True)).order_by(StaticPage.sort_order)
    )
    return list(result.scalars().all())


@router.get("/admin", response_model=list[PageRead])
async def list_all_pages(db: DBDep, _: CurrentUser) -> list[StaticPage]:
    result = await db.execute(select(StaticPage).order_by(StaticPage.sort_order))
    return list(result.scalars().all())


@router.get("/{slug}", response_model=PageRead)
async def get_page(slug: str, db: DBDep) -> StaticPage:
    result = await db.execute(
        select(StaticPage).where(StaticPage.slug == slug, StaticPage.is_published.is_(True))
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")
    return page


@router.post("", response_model=PageRead, status_code=201)
async def create_page(data: PageCreate, db: DBDep, _: CurrentUser) -> StaticPage:
    existing = await db.execute(select(StaticPage).where(StaticPage.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug '{data.slug}' bereits vergeben")
    page = StaticPage(**data.model_dump())
    db.add(page)
    await db.flush()
    return page


@router.put("/{slug}", response_model=PageRead)
async def update_page(slug: str, data: PageUpdate, db: DBDep, _: CurrentUser) -> StaticPage:
    result = await db.execute(select(StaticPage).where(StaticPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")
    dump = data.model_dump(exclude_none=True)
    new_slug = dump.get('slug')
    if new_slug is not None and new_slug != slug:
        existing = await db.execute(select(StaticPage).where(StaticPage.slug == new_slug))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail=f"Slug '{new_slug}' bereits vergeben")
    for field, value in dump.items():
        setattr(page, field, value)
    await db.flush()
    return page


@router.delete("/{slug}", status_code=204)
async def delete_page(slug: str, db: DBDep, _: CurrentUser) -> None:
    result = await db.execute(select(StaticPage).where(StaticPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")
    await db.delete(page)
