# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""robots.txt and llms.txt for the public portal domain.

Both are advisory only — well-behaved crawlers/LLM agents read them, nothing
enforces them technically. Actual abuse protection is the rate limiting in
core/limiter.py (see RATE_LIMIT_* settings), not these files.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from katalon.config import settings
from katalon.core.dependencies import DBDep
from katalon.core.models import PortalConfig

router = APIRouter(tags=["crawlers"])


@router.get("/robots.txt", response_class=PlainTextResponse, summary="robots.txt for the public portal")
async def robots_txt() -> str:
    lines = ["User-agent: *"]
    for path in settings.robots_disallow_paths:
        lines.append(f"Disallow: {path}")
    lines.append("Allow: /")
    return "\n".join(lines) + "\n"


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
        f"# {config.site_title}",
        "",
        config.site_subtitle or "GLAM metadata collection published with Katalon.",
        "",
        "## Structured data",
        "",
        f"- JSON-LD (CIDOC-CRM/LRMoo): `{base}/v1/{{type}}s/{{id}}/export?format=jsonld` "
        "or `Accept: application/ld+json` on the record's normal URL, where `{type}` is one of "
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
