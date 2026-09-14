# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from katalon.core.schemas import ExportProfileCapabilities
from katalon.services import metadata_format_service

router = APIRouter(prefix="/export-profiles", tags=["export-profiles"])


@router.get(
    "",
    response_model=list[ExportProfileCapabilities],
    summary="List all export capability profiles across registered formats",
)
async def list_export_profiles() -> list[ExportProfileCapabilities]:
    return await metadata_format_service.list_profiles()


@router.get(
    "/{format_key}/{profile_id}",
    response_model=ExportProfileCapabilities,
    summary="Get export capability profile by format_key and profile_id",
)
async def get_export_profile(
    format_key: str, profile_id: str
) -> ExportProfileCapabilities:
    profile = await metadata_format_service.get_profile(format_key, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Export-Profil '{profile_id}' für Format '{format_key}' nicht gefunden.",
        )
    return profile
