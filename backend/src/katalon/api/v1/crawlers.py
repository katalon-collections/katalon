# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""robots.txt and llms.txt for the public portal domain.

Both are advisory only — well-behaved crawlers/LLM agents read them, nothing
enforces them technically. Actual abuse protection is the rate limiting in
core/limiter.py (see RATE_LIMIT_* settings), not these files.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, literal, select, union_all

from katalon.config import settings
from katalon.core.dependencies import DBDep
from katalon.core.lang_text import resolve_lang_text
from katalon.core.models import PortalConfig
from katalon.core.visibility import PUBLIC_STATUSES
from katalon.integrations.jsonld_format import PLURAL_TYPE_MAP
from katalon.services.rdf_service import get_canonical_base_url
from katalon.services.seo_service import SEO_TYPES

router = APIRouter(tags=["crawlers"])


@router.get("/robots.txt", response_class=PlainTextResponse, summary="robots.txt for the public portal")
async def robots_txt() -> str:
    lines = ["User-agent: *"]
    for path in settings.robots_disallow_paths:
        lines.append(f"Disallow: {path}")
    lines.append("Allow: /")
    if settings.katalon_base_url.strip():
        lines += ["", f"Sitemap: {settings.katalon_base_url.strip().rstrip('/')}/sitemap.xml"]
    return "\n".join(lines) + "\n"


SITEMAP_PAGE_SIZE = 50_000  # sitemaps.org limit per file
_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def _public_records_query() -> Any:
    """(type, id, updated_at) of every publicly visible record, all types in one union."""
    return union_all(
        *(
            select(
                literal(record_type).label("type"), model.id.label("id"), model.updated_at.label("ts")
            ).where(model.deleted_at.is_(None), model.status.in_(PUBLIC_STATUSES))
            for record_type, (model, _) in SEO_TYPES.items()
        )
    ).subquery()


@router.get("/sitemap.xml", summary="sitemap.xml of all public records")
async def sitemap_xml(
    db: DBDep, request: Request, page: int = Query(0, ge=0)
) -> Response:
    """Single urlset up to 50,000 records, otherwise an index pointing to `?page=N`."""
    base = get_canonical_base_url(str(request.base_url))
    records = _public_records_query()
    total = (await db.execute(select(func.count()).select_from(records))).scalar_one()

    if page == 0 and total > SITEMAP_PAGE_SIZE:
        pages = -(-total // SITEMAP_PAGE_SIZE)
        body = "".join(
            f"<sitemap><loc>{base}/sitemap.xml?page={n}</loc></sitemap>" for n in range(1, pages + 1)
        )
        root = "sitemapindex"
    else:
        offset = max(page - 1, 0) * SITEMAP_PAGE_SIZE
        rows = await db.execute(
            select(records.c.type, records.c.id, records.c.ts)
            .order_by(records.c.type, records.c.id)
            .offset(offset)
            .limit(SITEMAP_PAGE_SIZE)
        )
        body = "".join(
            f"<url><loc>{base}/{PLURAL_TYPE_MAP[t]}/{rid}</loc>"
            f"<lastmod>{ts.date().isoformat()}</lastmod></url>"
            for t, rid, ts in rows
        )
        root = "urlset"
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<{root} xmlns="{_SITEMAP_NS}">{body}</{root}>\n'
    return Response(xml, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})


async def _portal_config(db: DBDep) -> PortalConfig:
    result = await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
    config = result.scalar_one_or_none()
    return config or PortalConfig(key="default")


@router.get("/llms.txt", response_class=PlainTextResponse, summary="llms.txt guidance for LLM agents")
async def llms_txt(db: DBDep) -> PlainTextResponse:
    if not settings.llms_txt_enabled:
        return PlainTextResponse("", status_code=404)

    config = await _portal_config(db)
    base = settings.katalon_base_url.rstrip("/") if settings.katalon_base_url else ""

    lines = [
        f"# {resolve_lang_text(config.site_title) or 'Katalon'}",
        "",
        resolve_lang_text(config.site_subtitle) or "GLAM metadata collection published with Katalon.",
        "",
        "## Structured data",
        "",
        f"- JSON-LD (CIDOC-CRM/LRMoo): `{base}/portal/v1/{{type}}s/{{id}}/export?format=jsonld` "
        "or `Accept: application/ld+json` on the record's normal API URL "
        f"(`{base}/portal/v1/{{type}}s/{{id}}`), where `{{type}}` is one of "
        "object, entity, place, occurrence, collection.",
        "- Turtle RDF: same endpoints with `?format=ttl` or `Accept: text/turtle`.",
        "",
        "## Access",
        "",
        "Only records with public status are exposed through these endpoints; no API key or "
        "authentication is required to read them. Records without public status return 404.",
        "",
        "## Rate limits",
        "",
        "Automated bulk access is rate-limited per IP address. Please respect HTTP 429 responses "
        "and back off; for large-scale harvesting, OAI-PMH is the intended bulk channel.",
    ]
    if settings.llms_txt_extra_notes:
        lines += ["", settings.llms_txt_extra_notes]
    return PlainTextResponse("\n".join(lines) + "\n")
