# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Literal

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from katalon.config import settings
from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import PortalConfig, User

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
    "site_title": {"de": "Katalon"},
    "site_subtitle": {},
    "hero_text": {},
    "featured_object_ids": [],
    "accent_color": "#1e3a8a",
    "logo_url": "",
    "placeholder_image_url": "",
    "facet_fields": {
        "object": [],
        "entity": [],
        "place": [],
        "occurrence": [],
        "procedure": [],
        "collection": [],
    },
    "subtitle_fields": {},
    "browse_enabled_types": ["object", "entity", "place", "occurrence", "collection"],
    "color_tokens": {},
    "detail_sidebar_position": "right",
    "meta_row_layout": "stacked",
    "meta_label_uppercase": False,
    "facet_sort": "count",
    "facet_sort_overrides": {},
    "facet_initial_count": 10,
    "homepage_blocks": [],
    "terminology": {},
    "show_iiif_manifest_link": True,
    "facet_order": {},
    "relation_facets": {},
    "footer": {},
    "notice": {},
    "header_show_title": True,
    "hero_hide_title": False,
}

TerminologyRecordType = Literal["object", "entity", "place", "occurrence", "collection"]

HomepageBlockType = Literal["text", "objects", "collections", "curated"]


class TerminologyEntry(BaseModel):
    """Portal-configurable singular/plural label override for one record type (#373).

    Presentation only — leaves record type keys, API routes/payloads, and
    permissions untouched. An empty dict for a language falls back to the
    portal's built-in default label for that type.
    """

    singular: dict[str, str] = Field(default_factory=dict)
    plural: dict[str, str] = Field(default_factory=dict)


class HomepageBlock(BaseModel):
    """One configurable homepage content block (issue #374).

    Fields are a flat union of all block-type options rather than a
    pydantic discriminated union — the set of types and options is small
    and a flat shape keeps admin-UI JSON diffing simple.
    """

    id: str
    type: HomepageBlockType
    enabled: bool = True
    title: dict[str, str] = Field(default_factory=dict)
    # type == "text"
    content: dict[str, str] | None = None
    # type == "objects" (recent) / "curated" (reads featured_object_ids)
    limit: int | None = Field(default=None, ge=1, le=100)
    # type == "collections"
    collections_mode: Literal["selected", "top", "all", "largest"] | None = None
    collection_ids: list[str] | None = None

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Block-ID darf nicht leer sein.")
        return value


def _safe_url(value: str) -> str:
    """Footer/notice links and images: http(s) URLs or site-relative paths
    only — never javascript:, data: or protocol-relative URLs."""
    value = value.strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    if value.lower().startswith(("https://", "http://")):
        return value
    raise ValueError("Nur http(s)-URLs oder Pfade, die mit / beginnen, sind erlaubt.")


class FooterLink(BaseModel):
    label: dict[str, str] = Field(default_factory=dict)
    url: str

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return _safe_url(value)


class FooterLogo(BaseModel):
    src: str
    alt: dict[str, str] = Field(default_factory=dict)
    href: str | None = None

    @field_validator("src")
    @classmethod
    def _check_src(cls, value: str) -> str:
        return _safe_url(value)

    @field_validator("href")
    @classmethod
    def _check_href(cls, value: str | None) -> str | None:
        return _safe_url(value) if value else None


class FooterColumn(BaseModel):
    """One footer column: Markdown text, a link list, or logos."""

    type: Literal["text", "links", "logos"]
    title: dict[str, str] = Field(default_factory=dict)
    content: dict[str, str] = Field(default_factory=dict)  # type == "text" (Markdown)
    links: list[FooterLink] = Field(default_factory=list)  # type == "links"
    include_footer_pages: bool = False  # type == "links": append pages placed in the footer
    logos: list[FooterLogo] = Field(default_factory=list)  # type == "logos"


class FooterBottom(BaseModel):
    text: dict[str, str] = Field(default_factory=dict)  # Markdown
    links: list[FooterLink] = Field(default_factory=list)


class FooterConfig(BaseModel):
    """Empty columns and bottom line: the portal keeps its one-line default footer."""

    columns: list[FooterColumn] = Field(default_factory=list, max_length=6)
    bottom: FooterBottom = Field(default_factory=FooterBottom)


class NoticeConfig(BaseModel):
    """One-time usage notice; shown once per browser and version."""

    enabled: bool = False
    version: int = Field(default=1, ge=1)
    title: dict[str, str] = Field(default_factory=dict)
    text: dict[str, str] = Field(default_factory=dict)  # Markdown
    accept_label: dict[str, str] = Field(default_factory=dict)


FacetRecordType = Literal["object", "entity", "place", "occurrence", "collection", "procedure"]


class RelationFacet(BaseModel):
    """A portal facet over linked records restricted to certain relation types,
    e.g. "Komponist_in" = entities linked via relation_type ``komponist``."""

    key: str = Field(pattern=r"^[a-z0-9_]{1,48}$")
    label: dict[str, str] = Field(default_factory=dict)
    target_type: Literal["entity", "place", "occurrence", "collection", "object"]
    relation_types: list[str] = Field(min_length=1)
    # Optional restriction on the linked record's subtype (e.g. occurrence "serie").
    target_subtypes: list[str] = Field(default_factory=list)
    # outgoing: this record → target; incoming: target → this record.
    direction: Literal["outgoing", "incoming", "both"] = "outgoing"


def _validate_relation_facets(
    value: dict[str, list[RelationFacet]] | None,
) -> dict[str, list[RelationFacet]] | None:
    for record_type, entries in (value or {}).items():
        keys = [entry.key for entry in entries]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Doppelte Facetten-Schlüssel für {record_type}.")
    return value


class PortalConfigRead(BaseModel):
    site_title: dict[str, str]
    site_subtitle: dict[str, str]
    hero_text: dict[str, str]
    featured_object_ids: list[str]
    facet_fields: dict[str, list[str]]
    subtitle_fields: dict[str, list[str]] = Field(default_factory=dict)
    browse_enabled_types: list[Literal["object", "entity", "place", "occurrence", "collection"]]
    accent_color: str
    logo_url: str
    placeholder_image_url: str
    color_tokens: dict[str, Any]
    detail_sidebar_position: Literal["left", "right"] = "right"
    meta_row_layout: Literal["stacked", "inline"] = "stacked"
    meta_label_uppercase: bool = False
    supported_languages: list[str] = ["de", "en"]
    facet_sort: Literal["count", "alpha"] = "count"
    facet_sort_overrides: dict[FacetRecordType, dict[str, Literal["count", "alpha"]]] = Field(
        default_factory=dict
    )
    facet_initial_count: int = 10
    homepage_blocks: list[HomepageBlock] = Field(default_factory=list)
    terminology: dict[TerminologyRecordType, TerminologyEntry] = Field(default_factory=dict)
    show_iiif_manifest_link: bool = True
    facet_order: dict[str, list[str]] = Field(default_factory=dict)
    relation_facets: dict[FacetRecordType, list[RelationFacet]] = Field(default_factory=dict)
    # Derived, read-only: kind (terms/numeric/boolean/date/tree/related/
    # inherited/relation) and display hints per facet name and record type.
    facet_kinds: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)
    footer: FooterConfig = Field(default_factory=FooterConfig)
    notice: NoticeConfig = Field(default_factory=NoticeConfig)
    header_show_title: bool = True
    hero_hide_title: bool = False

    model_config = ConfigDict(from_attributes=True)


class PortalConfigUpdate(BaseModel):
    site_title: dict[str, str] | None = None
    site_subtitle: dict[str, str] | None = None
    hero_text: dict[str, str] | None = None
    featured_object_ids: list[str] | None = None
    facet_fields: dict[str, list[str]] | None = None
    subtitle_fields: dict[str, list[str]] | None = None
    browse_enabled_types: (
        list[Literal["object", "entity", "place", "occurrence", "collection"]] | None
    ) = None
    accent_color: str | None = None
    logo_url: str | None = None
    placeholder_image_url: str | None = None
    color_tokens: dict[str, Any] | None = None
    detail_sidebar_position: Literal["left", "right"] | None = None
    meta_row_layout: Literal["stacked", "inline"] | None = None
    meta_label_uppercase: bool | None = None
    facet_sort: Literal["count", "alpha"] | None = None
    facet_sort_overrides: dict[FacetRecordType, dict[str, Literal["count", "alpha"]]] | None = None
    facet_initial_count: int | None = Field(default=None, ge=1, le=100)
    homepage_blocks: list[HomepageBlock] | None = None
    terminology: dict[TerminologyRecordType, TerminologyEntry] | None = None
    show_iiif_manifest_link: bool | None = None
    facet_order: dict[FacetRecordType, list[str]] | None = None
    relation_facets: dict[FacetRecordType, list[RelationFacet]] | None = None
    footer: FooterConfig | None = None
    notice: NoticeConfig | None = None
    header_show_title: bool | None = None
    hero_hide_title: bool | None = None

    @field_validator("relation_facets")
    @classmethod
    def _unique_relation_facet_keys(
        cls, value: dict[str, list[RelationFacet]] | None
    ) -> dict[str, list[RelationFacet]] | None:
        return _validate_relation_facets(value)


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
async def get_portal_config(db: DBDep) -> PortalConfigRead:
    from katalon.core.models import AdminConfig
    from katalon.services.facet_service import portal_facets

    config = await _get_or_create(db)
    # Direct facets come from the schema (is_facet), inherited/related ones from
    # the saved portal choice, relation facets from relation_facets — merged and
    # ordered by facet_order in facet_service.portal_facets.
    record_types = ("object", "entity", "place", "occurrence", "procedure", "collection")
    specs = await portal_facets(db, config, record_types)
    facet_fields: dict[str, list[str]] = {t: list(specs[t]) for t in record_types}
    facet_kinds = {
        t: {name: spec.public() for name, spec in specs[t].items()} for t in record_types
    }
    saved = config.facet_fields or {}
    configured_system_facets = saved.get("_system", ["record_type", "subtype"])
    facet_fields["_system"] = [
        name for name in ("record_type", "status", "subtype") if name in configured_system_facets
    ]
    # Apply defaults before validation so existing rows that predate a field
    # do not fail the non-null response schema.
    values = {
        field: value if (value := getattr(config, field, None)) is not None else default
        for field, default in _DEFAULTS.items()
    }
    result = PortalConfigRead.model_validate(values)
    result.facet_fields = facet_fields
    result.facet_kinds = facet_kinds
    lang_config = (
        await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    ).scalar_one_or_none()
    result.supported_languages = (
        lang_config.supported_languages
        if lang_config and lang_config.supported_languages
        else ["de", "en"]
    )
    return result


@router.put(
    "/config",
    response_model=PortalConfigRead,
    summary="Update the public portal configuration",
    responses={403: {"description": "Insufficient permissions"}},
)
async def update_portal_config(
    data: PortalConfigUpdate, db: DBDep, _: User = require_role("admin")
) -> PortalConfigRead:
    config = await _get_or_create(db)
    old_relation_facets = dict(config.relation_facets or {})
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    await db.flush()
    if data.relation_facets is not None:
        # Relation facets are materialized in the index: rebuild exactly the
        # record types whose definitions changed (coalesced, after commit).
        from katalon.workers.enqueue import after_commit
        from katalon.workers.reindex_state import request_bulk_reindex

        new_relation_facets = config.relation_facets or {}
        for record_type in set(old_relation_facets) | set(new_relation_facets):
            if old_relation_facets.get(record_type) != new_relation_facets.get(record_type):
                after_commit(db, request_bulk_reindex, record_type)
    return await get_portal_config(db)


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
async def upload_logo(file: UploadFile, db: DBDep, _: User = require_role("admin")) -> PortalConfig:
    if file.content_type not in _LOGO_ALLOWED:
        raise HTTPException(
            status_code=415, detail=f"Nicht unterstützter Dateityp: {file.content_type}"
        )

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


_FOOTER_ASSET_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
_FOOTER_ASSET_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|jpeg|png|webp|gif)$")


class FooterAssetRead(BaseModel):
    url: str


@router.post(
    "/footer-assets",
    response_model=FooterAssetRead,
    status_code=201,
    summary="Upload an image for the portal footer (e.g. a funder logo)",
    responses={
        403: {"description": "Insufficient permissions"},
        413: {"description": "File too large"},
        415: {"description": "Unsupported file type (raster images only, no SVG)"},
    },
)
async def upload_footer_asset(file: UploadFile, _: User = require_role("admin")) -> FooterAssetRead:
    # Raster images only: an SVG opened directly would run its scripts on the
    # portal origin (same reasoning as static page assets).
    suffix = Path(file.filename or "").suffix.lower()
    if file.content_type not in set(_FOOTER_ASSET_MIME.values()) or suffix not in _FOOTER_ASSET_MIME:
        raise HTTPException(status_code=415, detail="Erlaubt sind JPEG, PNG, WebP und GIF.")
    target_dir = Path(settings.media_root) / "portal-assets"
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    size = 0
    async with aiofiles.open(target_dir / name, "wb") as out:
        while chunk := await file.read(65536):
            size += len(chunk)
            if size > 5 * 1024 * 1024:
                await out.close()
                (target_dir / name).unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Maximal 5 MB.")
            await out.write(chunk)
    return FooterAssetRead(url=f"/portal/v1/portal/footer-assets/{name}")


async def serve_footer_asset(name: str) -> FileResponse:
    """Public download of an uploaded footer image (routed in portal_public)."""
    if not _FOOTER_ASSET_NAME.match(name):
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    path = Path(settings.media_root) / "portal-assets" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    return FileResponse(path, media_type=_FOOTER_ASSET_MIME[path.suffix])


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
