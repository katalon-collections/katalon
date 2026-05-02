import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from katalon.config import settings

router = APIRouter(prefix="/theme", tags=["theme"])

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
    },
    "fonts": {"body": None, "mono": None},
    "logo": None,
    "favicon": None,
}


@router.get("")
async def get_theme() -> JSONResponse:
    """Return active theme manifest. Falls back to defaults if no theme configured."""
    theme_name = getattr(settings, "portal_theme", None)
    if theme_name:
        theme_file = Path(settings.media_root).parent / "themes" / theme_name / "theme.json"
        if theme_file.exists():
            data = json.loads(theme_file.read_text())
            return JSONResponse(content=data)
    return JSONResponse(content=_DEFAULTS)
