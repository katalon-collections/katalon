# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import logging
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from katalon.core.dependencies import DBDep, require_feature
from katalon.core.media_storage import (
    LocalStorage,
    get_storage,
    page_asset_storage_key,
    safe_filename,
)
from katalon.core.media_validation import resolve_page_asset_mime, verify_page_asset
from katalon.core.models import PageAsset, StaticPage, User

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
_PLACEMENTS = {'header', 'footer', 'none'}
MAX_PAGE_ASSET_SIZE = 100 * 1024 * 1024  # 100 MB

router = APIRouter(prefix="/pages", tags=["pages"])


class PageCreate(BaseModel):
    slug: str
    title: dict[str, Any] = {}
    content: dict[str, Any] = {}
    is_published: bool = False
    placement: str = "footer"
    sort_order: int = 0

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError('Slug muss URL-sicher sein (nur Kleinbuchstaben, Zahlen, Bindestriche)')
        return v

    @field_validator('placement')
    @classmethod
    def validate_placement(cls, v: str) -> str:
        if v not in _PLACEMENTS:
            raise ValueError('placement muss "header", "footer" oder "none" sein')
        return v


class PageUpdate(BaseModel):
    title: dict[str, Any] | None = None
    content: dict[str, Any] | None = None
    is_published: bool | None = None
    placement: str | None = None
    sort_order: int | None = None

    @field_validator('placement')
    @classmethod
    def validate_placement(cls, v: str | None) -> str | None:
        if v is not None and v not in _PLACEMENTS:
            raise ValueError('placement muss "header", "footer" oder "none" sein')
        return v


class PageRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    slug: str
    title: dict[str, Any]
    content: dict[str, Any]
    is_published: bool
    placement: str
    sort_order: int


class PageAssetRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    page_id: uuid.UUID
    filename: str
    mime_type: str
    file_size: int
    url: str
    created_at: datetime


def serialize_page_asset(asset: PageAsset) -> dict[str, Any]:
    encoded_filename = quote(asset.filename, safe="")
    return {
        "id": asset.id,
        "page_id": asset.page_id,
        "filename": asset.filename,
        "mime_type": asset.mime_type,
        "file_size": asset.file_size,
        "url": f"/portal/v1/pages/assets/{asset.id}/{encoded_filename}",
        "created_at": asset.created_at or datetime.now(),
    }


async def serve_page_asset(
    asset_id: uuid.UUID,
    filename: str,
    db: DBDep,
    as_attachment: bool = False,
) -> Response:
    result = await db.execute(select(PageAsset).where(PageAsset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")

    storage = get_storage()
    disposition = "attachment" if as_attachment else "inline"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{asset.filename}"',
        "Cache-Control": "public, max-age=86400",
    }
    if isinstance(storage, LocalStorage):
        path = storage.local_path(asset.storage_key)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Datei nicht gefunden")
        return FileResponse(
            path,
            media_type=asset.mime_type,
            filename=asset.filename,
            content_disposition_type=disposition,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    if not storage.exists(asset.storage_key):
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return StreamingResponse(
        storage.stream(asset.storage_key),
        media_type=asset.mime_type,
        headers=headers,
    )


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
async def list_all_pages(db: DBDep, _: User = require_feature("pages")) -> list[StaticPage]:
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
async def create_page(data: PageCreate, db: DBDep, _: User = require_feature("pages")) -> StaticPage:
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
async def update_page(slug: str, data: PageUpdate, db: DBDep, _: User = require_feature("pages")) -> StaticPage:
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
async def delete_page(slug: str, db: DBDep, _: User = require_feature("pages")) -> None:
    result = await db.execute(
        select(StaticPage).options(selectinload(StaticPage.assets)).where(StaticPage.slug == slug)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")

    storage = get_storage()
    keys_to_delete = [asset.storage_key for asset in page.assets]
    if keys_to_delete:
        try:
            await storage.delete(*keys_to_delete)
        except Exception as exc:
            logger.warning("Fehler beim physischen Löschen der Page-Assets: %s", exc)

    await db.delete(page)


# ---------------------------------------------------------------------------
# Page assets (images, PDFs, MP4 videos)
# ---------------------------------------------------------------------------


@router.get(
    "/{slug}/assets",
    response_model=list[PageAssetRead],
    summary="List assets for a static page",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Page not found"},
    },
)
async def list_page_assets(
    slug: str, db: DBDep, _: User = require_feature("pages")
) -> list[PageAssetRead]:
    result = await db.execute(select(StaticPage).where(StaticPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")

    res = await db.execute(
        select(PageAsset)
        .where(PageAsset.page_id == page.id)
        .order_by(PageAsset.created_at.desc())
    )
    return [PageAssetRead(**serialize_page_asset(a)) for a in res.scalars().all()]


@router.post(
    "/{slug}/assets",
    response_model=PageAssetRead,
    status_code=201,
    summary="Upload an asset for a static page",
    responses={
        400: {"description": "Missing filename"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Page not found"},
        413: {"description": "File too large"},
        415: {"description": "Unsupported media type"},
    },
)
async def upload_page_asset(
    slug: str,
    file: UploadFile,
    db: DBDep,
    _: User = require_feature("pages"),
) -> PageAssetRead:
    result = await db.execute(select(StaticPage).where(StaticPage.slug == slug))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")

    orig_filename = file.filename or ""
    if not orig_filename.strip():
        raise HTTPException(status_code=400, detail="Dateiname fehlt")

    initial_mime = resolve_page_asset_mime(file.content_type, orig_filename)
    asset_id = uuid.uuid4()
    cleaned_name = safe_filename(orig_filename)
    key = page_asset_storage_key(asset_id, cleaned_name)
    storage = get_storage()

    size = 0
    if isinstance(storage, LocalStorage):
        dest_path = storage.local_path(key)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with dest_path.open("wb") as buffer:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_PAGE_ASSET_SIZE:
                        raise HTTPException(status_code=413, detail="Datei zu groß (maximal 100 MB)")
                    buffer.write(chunk)
            actual_mime = verify_page_asset(dest_path, initial_mime)
        except Exception:
            dest_path.unlink(missing_ok=True)
            raise
    else:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            try:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_PAGE_ASSET_SIZE:
                        raise HTTPException(status_code=413, detail="Datei zu groß (maximal 100 MB)")
                    tmp.write(chunk)
                tmp.flush()
                actual_mime = verify_page_asset(tmp_path, initial_mime)
                await storage.put_file(key, tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)

    asset = PageAsset(
        id=asset_id,
        page_id=page.id,
        filename=cleaned_name,
        mime_type=actual_mime,
        file_size=size,
        storage_key=key,
        created_at=datetime.now(),
    )
    db.add(asset)
    await db.flush()
    return PageAssetRead(**serialize_page_asset(asset))


@router.delete(
    "/{slug}/assets/{asset_id}",
    status_code=204,
    summary="Delete an asset from a static page",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Asset or page not found"},
    },
)
async def delete_page_asset(
    slug: str,
    asset_id: uuid.UUID,
    db: DBDep,
    _: User = require_feature("pages"),
) -> None:
    page_res = await db.execute(select(StaticPage).where(StaticPage.slug == slug))
    page = page_res.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Seite nicht gefunden")

    asset_res = await db.execute(
        select(PageAsset).where(PageAsset.id == asset_id, PageAsset.page_id == page.id)
    )
    asset = asset_res.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset nicht gefunden")

    storage = get_storage()
    try:
        await storage.delete(asset.storage_key)
    except Exception as exc:
        logger.warning("Fehler beim physischen Löschen des Assets: %s", exc)

    await db.delete(asset)


@router.get(
    "/assets/{asset_id}/{filename}",
    summary="Serve a static page asset file",
    responses={404: {"description": "Asset not found"}},
)
async def serve_page_asset_endpoint(
    asset_id: uuid.UUID,
    filename: str,
    db: DBDep,
) -> Response:
    return await serve_page_asset(asset_id, filename, db)
