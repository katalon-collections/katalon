# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import json
import logging
import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from katalon.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/theme", tags=["theme"])

# theme.json "script": a .js file inside the theme directory (no "..", no
# absolute or external URL) — the portal loads it from /themes/<name>/ only,
# matching the CSP script-src 'self'.
_SCRIPT_RE = re.compile(r"^(?!.*\.\.)[A-Za-z0-9_][A-Za-z0-9_./-]*\.js$")

_DEFAULTS = {
    "name": "Katalon",
    "tokens": {
        "--accent":     "#1e3a8a",
        "--accent-50":  "#eef2fb",
        "--accent-100": "#dde3f5",
        "--accent-ink": "#15296b",
        "--bg":         "#f4f5f7",
        "--panel":      "#ffffff",
        "--fg":         "#181a1f",
        "--header-bg":  "#0b1a33",
        "--header-fg":  "#ffffff",
        "--viewer-bg":  "#0f172a",
    },
    "fonts": {"body": None, "mono": None},
    "logo": None,
    "favicon": None,
}


@router.get("", summary="Get the active portal theme manifest (falls back to defaults)")
async def get_theme() -> JSONResponse:
    """Return active theme manifest. Falls back to defaults if no theme configured."""
    theme_name = getattr(settings, "portal_theme", None)
    if theme_name:
        theme_file = Path(settings.media_root).parent / "themes" / theme_name / "theme.json"
        if theme_file.exists():
            data = json.loads(theme_file.read_text())
            # The portal loads theme files from /themes/<directory>/.
            data["directory"] = theme_name
            script = data.get("script")
            if script is not None and not (isinstance(script, str) and _SCRIPT_RE.match(script)):
                logger.warning("theme %s: ignoring invalid script path %r", theme_name, script)
                data.pop("script", None)
            return JSONResponse(content=data)
    return JSONResponse(content=_DEFAULTS)
