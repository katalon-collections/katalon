from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from katalon.core.dependencies import DBDep, require_admin
from katalon.core.models import StaticPage, User

_SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

router = APIRouter(prefix="/pages", tags=["pages"])


class PageCreate(BaseModel):
    slug: str
    title: dict[str, Any] = {}
    content: dict[str, Any] = {}
    is_published: bool = False
    sort_order: int = 0

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError('Slug muss URL-sicher sein (nur Kleinbuchstaben, Zahlen, Bindestriche)')
        return v


class PageUpdate(BaseModel):
    title: dict[str, Any] | None = None
    content: dict[str, Any] | None = None
    is_published: bool | None = None
    sort_order: int | None = None


class PageRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    slug: str
    title: dict[str, Any]
    content: dict[str, Any]
    is_published: bool
    sort_order: int


@router.get("", response_model=list[PageRead], summary="List published static pages")
async def list_pages(db: DBDep) -> list[StaticPage]:
    result = await db.execute(
        select(StaticPage).where(StaticPage.is_published.is_(True)).order_by(StaticPage.sort_order)
    )
    return list(result.scalars().all())


@router.get(
    "/admin",
    response_model=list[PageRead],
    summary="List all static pages including unpublished",
    responses={403: {"description": "Insufficient permissions"}},
)
async def list_all_pages(db: DBDep, _: User = require_admin()) -> list[StaticPage]:
    result = await db.execute(select(StaticPage).order_by(StaticPage.sort_order))
    return list(result.scalars().all())


@router.get(
    "/{slug}",
    response_model=PageRead,
    summary="Get a published static page by slug",
    responses={404: {"description": "Page not found"}},
)
async def get_page(slug: str, db: DBDep) -> StaticPage:
    result = await db.execute(
        select(StaticPage).where(StaticPage.slug == slug, StaticPage.is_published.is_(True))
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")
    return page


@router.post(
    "",
    response_model=PageRead,
    status_code=201,
    summary="Create a new static page",
    responses={
        403: {"description": "Insufficient permissions"},
        409: {"description": "Slug already in use"},
    },
)
async def create_page(data: PageCreate, db: DBDep, _: User = require_admin()) -> StaticPage:
    existing = await db.execute(select(StaticPage).where(StaticPage.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug '{data.slug}' bereits vergeben")
    page = StaticPage(**data.model_dump())
    db.add(page)
    await db.flush()
    return page


@router.put(
    "/{slug}",
    response_model=PageRead,
    summary="Update a static page",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Page not found"},
        409: {"description": "Slug already in use"},
    },
)
async def update_page(slug: str, data: PageUpdate, db: DBDep, _: User = require_admin()) -> StaticPage:
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


@router.delete(
    "/{slug}",
    status_code=204,
    summary="Delete a static page",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Page not found"},
    },
)
async def delete_page(slug: str, db: DBDep, _: User = require_admin()) -> None:
    result = await db.execute(select(StaticPage).where(StaticPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")
    await db.delete(page)
