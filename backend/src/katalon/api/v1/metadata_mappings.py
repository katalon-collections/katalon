# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from fastapi import APIRouter

from katalon.core.schemas import FormatOut
from katalon.services import metadata_format_service

router = APIRouter(prefix="/metadata-mappings", tags=["metadata-mappings"])


@router.get(
    "/formats",
    response_model=list[FormatOut],
    summary="List registered export formats and their mappable targets",
)
async def list_formats() -> list[FormatOut]:
    formats = await metadata_format_service.list_formats()
    return [
        FormatOut(
            key=f.key,
            label=f.label,
            targets=sorted(f.targets),
            capabilities=f.capabilities(),
        )
        for f in formats
    ]
