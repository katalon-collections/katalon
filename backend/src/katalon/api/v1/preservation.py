# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from katalon.core.dependencies import DBDep, require_feature
from katalon.services import preservation_service

router = APIRouter(
    prefix="/preservation",
    tags=["preservation"],
    dependencies=[require_feature("export")],
)


@router.get(
    "/objects/{object_id}/bag",
    summary="Download a BagIt preservation package (ZIP) for one object",
)
async def export_preservation_bag(object_id: uuid.UUID, db: DBDep) -> Response:
    try:
        filename, content = await preservation_service.build_object_preservation_zip(db, object_id)
    except preservation_service.PreservationExportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
