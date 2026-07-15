from __future__ import annotations

from pathlib import Path

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from katalon.config import settings
from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import PortalConfig

_LOGO_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
_LOGO_ALLOWED = set(_LOGO_MIME.values())
_LOGO_URL = "/v1/portal/logo/file"

router = APIRouter(prefix="/portal", tags=["portal"])

_DEFAULTS = {
    "site_title": "Katalon",
    "site_subtitle": "",
    "hero_text": "",
    "featured_object_ids": [],
    "accent_color": "#1e3a8a",
    "logo_url": "",
    "placeholder_image_url": "",
    "facet_fields": {"object": [], "entity": [], "place": [], "occurrence": []},
    "color_tokens": {},
}


class PortalConfigRead(BaseModel):
    site_title: str
    site_subtitle: str
    hero_text: str
    featured_object_ids: list[str]
    facet_fields: dict[str, list[str]]
    accent_color: str
    logo_url: str
    placeholder_image_url: str
    color_tokens: dict

    class Config:
        from_attributes = True


class PortalConfigUpdate(BaseModel):
    site_title: str | None = None
    site_subtitle: str | None = None
    hero_text: str | None = None
    featured_object_ids: list[str] | None = None
    facet_fields: dict[str, list[str]] | None = None
    accent_color: str | None = None
    logo_url: str | None = None
    placeholder_image_url: str | None = None
    color_tokens: dict | None = None


async def _get_or_create(db: DBDep) -> PortalConfig:
    result = await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
    config = result.scalar_one_or_none()
    if config is None:
        config = PortalConfig(key="default")
        db.add(config)
        await db.flush()
    return config


@router.get(
    "/config",
    response_model=PortalConfigRead,
    summary="Get the public portal configuration",
)
async def get_portal_config(db: DBDep) -> PortalConfig:
    from katalon.core.models import FieldDefinition

    config = await _get_or_create(db)
    # Build facet_fields dynamically from field_definitions.is_facet
    facet_result = await db.execute(
        select(FieldDefinition.target_type, FieldDefinition.name).where(
            FieldDefinition.is_facet.is_(True),
            FieldDefinition.is_deleted.is_(False),
        )
    )
    facet_fields: dict[str, list[str]] = {"object": [], "entity": [], "place": [], "occurrence": []}
    for row in facet_result.all():
        facet_fields.setdefault(row.target_type, []).append(row.name)
    config.facet_fields = facet_fields
    return config


@router.put(
    "/config",
    response_model=PortalConfigRead,
    summary="Update the public portal configuration",
    responses={403: {"description": "Insufficient permissions"}},
)
async def update_portal_config(
    data: PortalConfigUpdate, db: DBDep, _=require_role("admin")
) -> PortalConfig:
    config = await _get_or_create(db)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    await db.flush()
    return config


@router.post(
    "/logo",
    response_model=PortalConfigRead,
    status_code=200,
    summary="Upload the portal logo",
    responses={
        415: {"description": "Unsupported file type"},
        403: {"description": "Insufficient permissions"},
    },
)
async def upload_logo(file: UploadFile, db: DBDep, _=require_role("admin")) -> PortalConfig:
    if file.content_type not in _LOGO_ALLOWED:
        raise HTTPException(status_code=415, detail=f"Nicht unterstützter Dateityp: {file.content_type}")

    logo_dir = Path(settings.media_root) / "logos"
    logo_dir.mkdir(parents=True, exist_ok=True)

    for old in logo_dir.glob("logo.*"):
        old.unlink(missing_ok=True)

    suffix = Path(file.filename or "logo").suffix.lower() or ".png"
    dest = logo_dir / f"logo{suffix}"

    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(65536):
            await out.write(chunk)

    config = await _get_or_create(db)
    config.logo_url = _LOGO_URL
    await db.flush()
    return config


@router.get(
    "/logo/file",
    summary="Serve the uploaded portal logo file",
    responses={404: {"description": "No logo uploaded"}},
)
async def serve_logo() -> FileResponse:
    logo_dir = Path(settings.media_root) / "logos"
    candidates = sorted(logo_dir.glob("logo.*")) if logo_dir.exists() else []
    if not candidates:
        raise HTTPException(status_code=404, detail="Kein Logo hochgeladen")
    logo_file = candidates[0]
    mime = _LOGO_MIME.get(logo_file.suffix.lower(), "image/png")
    return FileResponse(logo_file, media_type=mime)
