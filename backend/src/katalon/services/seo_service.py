# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Meta-tag HTML for crawlers that do not execute the portal SPA.

nginx routes known link-preview, search and AI bots to this renderer instead of
the SPA shell (see `$seo_bot` in docker/nginx.conf). Everything comes from the
anonymous public projection, never from raw record metadata.
"""

from __future__ import annotations

import html
import json
import re
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.lang_text import resolve_lang_text
from katalon.core.media_storage import iiif_identifier
from katalon.core.media_validation import media_category
from katalon.core.models import (
    Collection,
    Entity,
    Object,
    Occurrence,
    Place,
    PortalConfig,
)
from katalon.core.thumbnails import THUMBNAIL_HEIGHT_HIDPI, thumbnail_path
from katalon.core.visibility import PUBLIC_STATUSES
from katalon.integrations.jsonld_format import PLURAL_TYPE_MAP, map_primary_type
from katalon.services.media_service import primary_media_files_by_object
from katalon.services.public_metadata_service import (
    filter_public_metadata_checked,
    load_public_fields,
)
from katalon.services.rdf_service import get_canonical_base_url
from katalon.services.search_service import _extract_title

SEO_TYPES: dict[str, tuple[Any, str]] = {
    "object": (Object, "object_type"),
    "entity": (Entity, "entity_type"),
    "place": (Place, "place_type"),
    "occurrence": (Occurrence, "occurrence_type"),
    "collection": (Collection, "collection_type"),
}

# schema.org type per CIDOC-CRM/LRMoo class chosen by `map_primary_type`.
_SCHEMA_TYPES = {
    "crm:E22_Human-Made_Object": "CreativeWork",
    "crm:E21_Person": "Person",
    "crm:E74_Group": "Organization",
    "crm:E53_Place": "Place",
    "crm:E5_Event": "Event",
    "crm:E78_Curated_Holding": "Collection",
}

DESCRIPTION_FIELDS = ("description", "kurzbeschreibung")
DESCRIPTION_MAX = 200

_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MARKDOWN_MARKS = re.compile(r"[*_`#>]+")


def _text(value: Any) -> str:
    """First plain string of a metadata value (plain, `{value}` or repeatable list)."""
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("value") or value.get("label")
    return value.strip() if isinstance(value, str) else ""


def _teaser(text: str) -> str:
    text = _MARKDOWN_MARKS.sub("", _MARKDOWN_LINK.sub(r"\1", text))
    text = " ".join(text.split())
    if len(text) <= DESCRIPTION_MAX:
        return text
    return text[:DESCRIPTION_MAX].rsplit(" ", 1)[0].rstrip(",;:.") + "…"


def _schema_type(record_type: str, subtype: str | None) -> str:
    cidoc = map_primary_type(record_type, subtype)
    if isinstance(cidoc, list):
        cidoc = cidoc[0]
    return "CreativeWork" if cidoc.startswith("lrmoo:") else _SCHEMA_TYPES.get(cidoc, "Thing")


def build_seo_html(
    *,
    record_type: str,
    record_id: str,
    idno: str | None,
    subtype: str | None,
    metadata: dict[str, Any],
    site_name: str,
    base_url: str,
    image_url: str = "",
) -> str:
    title = _extract_title(metadata) or idno or record_id
    description = ""
    for field in DESCRIPTION_FIELDS:
        description = _teaser(_text(metadata.get(field)))
        if description:
            break
    url = f"{base_url}/{PLURAL_TYPE_MAP[record_type]}/{record_id}" if base_url else ""
    full_title = f"{title} | {site_name}" if site_name else title

    tags = [f"<title>{html.escape(full_title)}</title>"]

    def meta(attr: str, name: str, content: str) -> None:
        if content:
            tags.append(f'<meta {attr}="{name}" content="{html.escape(content, quote=True)}">')

    if url:
        tags.append(f'<link rel="canonical" href="{html.escape(url, quote=True)}">')
    meta("name", "description", description)
    meta("property", "og:site_name", site_name)
    meta("property", "og:title", full_title)
    meta("property", "og:description", description)
    meta("property", "og:url", url)
    meta("property", "og:type", "article")
    meta("property", "og:image", image_url)
    meta("name", "twitter:card", "summary_large_image" if image_url else "summary")
    meta("name", "twitter:title", full_title)
    meta("name", "twitter:description", description)
    meta("name", "twitter:image", image_url)

    ld: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": _schema_type(record_type, subtype),
        "name": title,
    }
    for key, val in (("description", description), ("image", image_url), ("url", url),
                     ("identifier", idno)):
        if val:
            ld[key] = val
    # "</" would end the script element early.
    ld_json = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    tags.append(f'<script type="application/ld+json">{ld_json}</script>')

    body = f"<h1>{html.escape(title)}</h1>"
    if description:
        body += f"<p>{html.escape(description)}</p>"
    return (
        '<!doctype html>\n<html><head><meta charset="utf-8">\n'
        + "\n".join(tags)
        + f"\n</head><body>{body}</body></html>\n"
    )


async def render_record_seo(
    db: AsyncSession, record_type: str, record_id: uuid.UUID, request_base_url: str = ""
) -> str:
    """Meta-tag HTML for one public record; 404 for anything not publicly visible."""
    if record_type not in SEO_TYPES:
        raise HTTPException(status_code=404, detail="Datensatztyp unbekannt")
    model, subtype_attr = SEO_TYPES[record_type]
    record = (
        await db.execute(
            select(model).where(
                model.id == record_id,
                model.deleted_at.is_(None),
                model.status.in_(PUBLIC_STATUSES),
            )
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Datensatz nicht gefunden")

    subtype = getattr(record, subtype_attr, None)
    fields = await load_public_fields(db, record_type)
    metadata = await filter_public_metadata_checked(db, record.metadata_, fields, subtype)

    config = (
        await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
    ).scalar_one_or_none()
    site_name = resolve_lang_text(config.site_title) if config else ""
    base_url = get_canonical_base_url(request_base_url)

    image_url = ""
    if record_type == "object" and base_url:
        preview = (await primary_media_files_by_object(db, [record.id], public_only=True)).get(record.id)
        if preview and media_category(preview.mime_type) == "image":
            identifier = iiif_identifier(preview.iiif_storage_key, preview.storage_key)
            path = thumbnail_path(identifier, THUMBNAIL_HEIGHT_HIDPI)
            image_url = f"{base_url}{path}"

    return build_seo_html(
        record_type=record_type,
        record_id=str(record.id),
        idno=record.idno,
        subtype=subtype,
        metadata=metadata,
        site_name=site_name or "",
        base_url=base_url,
        image_url=image_url,
    )
