from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from katalon.config import settings
from katalon.core.dependencies import DBDep
from katalon.services.ark_service import resolve_ark

router = APIRouter(tags=["ark"])


@router.get("/ark:/{naan}/{suffix}", include_in_schema=False)
async def resolve(naan: str, suffix: str, db: DBDep) -> RedirectResponse:
    """Redirect a public ARK to the current portal record URL.

    Resolution remains available when minting is disabled so existing citations
    continue to work. The reserved NAAN 99999 is never a public namespace.
    """
    configured_naan = settings.ark_naan.strip()
    if not configured_naan or configured_naan == "99999" or naan != configured_naan:
        raise HTTPException(status_code=404, detail="ARK nicht gefunden.")
    target = await resolve_ark(db, f"ark:/{naan}/{suffix}")
    if target is None:
        raise HTTPException(status_code=404, detail="ARK nicht gefunden.")
    return RedirectResponse(target, status_code=303)
