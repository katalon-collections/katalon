# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from katalon.core.dependencies import DBDep, OptionalCurrentUser, require_feature
from katalon.core.schemas import RECORD_TYPES
from katalon.services import export_service, metadata_format_service
from katalon.services.metadata_mapping_service import mapped_record_types

router = APIRouter(prefix="/export", tags=["export"], dependencies=[require_feature("export")])

MEDIA_TYPES = {"csv": "text/csv", "json": "application/json", "xml": "application/xml"}


class FormatOut(BaseModel):
    key: str
    label: str
    kind: str  # "flat" | "xml" | "graph"


@router.get(
    "/formats",
    response_model=list[FormatOut],
    summary="List export formats available for a record type",
)
async def list_formats(db: DBDep, record_type: str = Query(...)) -> list[FormatOut]:
    if record_type not in RECORD_TYPES:
        raise HTTPException(status_code=404, detail=f"Unbekannter Typ: {record_type}")

    formats = [FormatOut(key="csv", label="CSV", kind="flat"), FormatOut(key="json", label="JSON", kind="flat")]
    for fmt in await metadata_format_service.list_formats():
        if record_type in await mapped_record_types(db, fmt.key):
            kind = "graph" if fmt.key == "json_ld" else "xml"
            formats.append(FormatOut(key=fmt.key, label=fmt.label, kind=kind))
    return formats


@router.get(
    "/{record_type}",
    summary="Download a data dump for a record type",
)
async def export_records(
    record_type: str,
    db: DBDep,
    format: str = Query(...),
    subtype: str | None = Query(None),
) -> StreamingResponse:
    if record_type not in RECORD_TYPES:
        raise HTTPException(status_code=404, detail=f"Unbekannter Typ: {record_type}")

    filename = f"{record_type}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    if format == "csv":
        return StreamingResponse(
            export_service.stream_csv(db, record_type, subtype),
            media_type=MEDIA_TYPES["csv"],
            headers=headers,
        )
    if format == "json":
        return StreamingResponse(
            export_service.stream_json(db, record_type, subtype),
            media_type=MEDIA_TYPES["json"],
            headers=headers,
        )

    if record_type not in await mapped_record_types(db, format):
        raise HTTPException(
            status_code=422,
            detail=f"Format '{format}' hat keine Feld-Mappings für Typ '{record_type}'.",
        )
    return StreamingResponse(
        export_service.stream_xml(db, record_type, format),
        media_type=MEDIA_TYPES["xml"],
        headers={"Content-Disposition": f'attachment; filename="{record_type}.{format}.xml"'},
    )


@router.get(
    "/{record_type}/{record_id}",
    summary="Export a single record as JSON-LD or Turtle RDF",
)
@router.get(
    "/{record_type}/{record_id}/export",
    summary="Export a single record as JSON-LD or Turtle RDF",
)
async def export_single_record_route(
    record_type: str,
    record_id: uuid.UUID,
    db: DBDep,
    request: Request,
    current_user: OptionalCurrentUser,
    format: str | None = Query(None),
    accept: str | None = Header(None),
) -> Response:
    from katalon.services.rdf_service import handle_single_record_export

    return await handle_single_record_export(
        record_type,
        record_id,
        db,
        request,
        current_user=current_user,
        format_param=format,
        accept_header=accept,
    )
