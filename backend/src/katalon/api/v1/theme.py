# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from katalon.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/theme", tags=["theme"])

# theme.json "script": a .js file inside the theme directory (no "..", no
# absolute or external URL) — the portal loads it from /themes/<name>/ only,
# matching the CSP script-src 'self'.
_SCRIPT_RE = re.compile(r"^(?!.*\.\.)[A-Za-z0-9_][A-Za-z0-9_./-]*\.js$")

# theme.css: custom property names and values that cannot leave the
# declaration, and a stylesheet that is a same-origin path or an https URL.
_TOKEN_NAME_RE = re.compile(r"^--[A-Za-z0-9_-]+$")
_TOKEN_VALUE_RE = re.compile(r"^[^;{}<>\\\n\r]+$")
_STYLESHEET_RE = re.compile(r"^(?:/(?!/)|https://)[^\s\"'()\\]+$")

# Portal config accent_color default — it overrides the theme only once changed.
_DEFAULT_ACCENT = "#1e3a8a"

_DEFAULT_TOKENS: dict[str, str] = {
    "--accent":     "#1e3a8a",
    "--accent-50":  "#eef2fb",
    "--accent-100": "#dde3f5",
    "--accent-ink": "#15296b",
    "--bg":         "#f4f5f7",
    "--panel":      "#ffffff",
    "--panel-2":    "#fafbfc",
    "--border":     "#e4e6eb",
    "--fg":         "#181a1f",
    "--fg-2":       "#3a4150",
    "--fg-3":       "#5a6173",
    "--fg-4":       "#677083",
    "--header-bg":  "#0b1a33",
    "--header-fg":  "#ffffff",
    # Dark stage behind the IIIF viewer, media player and media thumbnails.
    "--viewer-bg":  "#0f172a",
}

_DEFAULTS: dict[str, Any] = {
    "name": "Katalon",
    "tokens": _DEFAULT_TOKENS,
    "fonts": {"body": None, "mono": None},
    "logo": None,
    "favicon": None,
}


def load_theme() -> dict[str, Any]:
    """Active theme manifest, or the defaults if no theme is configured."""
    theme_name = getattr(settings, "portal_theme", None)
    if theme_name:
        theme_file = Path(settings.media_root).parent / "themes" / theme_name / "theme.json"
        if theme_file.exists():
            data: dict[str, Any] = json.loads(theme_file.read_text())
            # The portal loads theme files from /themes/<directory>/.
            data["directory"] = theme_name
            script = data.get("script")
            if script is not None and not (isinstance(script, str) and _SCRIPT_RE.match(script)):
                logger.warning("theme %s: ignoring invalid script path %r", theme_name, script)
                data.pop("script", None)
            return data
    return _DEFAULTS


def theme_css(
    manifest: dict[str, Any],
    color_tokens: dict[str, Any] | None = None,
    accent_color: str | None = None,
) -> str:
    """Stylesheet the portal links render-blocking in <head>, so the first paint
    already carries the theme: the theme's stylesheet (fonts.body) as @import,
    then the tokens — defaults, theme tokens, portal config overrides."""
    tokens: dict[str, Any] = {**_DEFAULT_TOKENS, **(manifest.get("tokens") or {})}
    tokens.update({k: v for k, v in (color_tokens or {}).items() if v})
    if accent_color and accent_color.lower() != _DEFAULT_ACCENT:
        tokens["--accent"] = accent_color

    lines: list[str] = []
    stylesheet = (manifest.get("fonts") or {}).get("body")
    if isinstance(stylesheet, str) and _STYLESHEET_RE.match(stylesheet):
        lines.append(f'@import url("{stylesheet}");')
    elif stylesheet:
        logger.warning("theme: ignoring invalid stylesheet %r", stylesheet)
    declarations = [
        f"  {name}: {value};"
        for name, value in tokens.items()
        if isinstance(value, str) and _TOKEN_NAME_RE.match(name) and _TOKEN_VALUE_RE.match(value)
    ]
    # :root:root outranks a plain :root in the app stylesheet, whatever the order.
    lines += [":root:root {", *declarations, "}"]
    return "\n".join(lines) + "\n"


@router.get("", summary="Get the active portal theme manifest (falls back to defaults)")
async def get_theme() -> JSONResponse:
    """Return active theme manifest. Falls back to defaults if no theme configured."""
    return JSONResponse(content=load_theme())
