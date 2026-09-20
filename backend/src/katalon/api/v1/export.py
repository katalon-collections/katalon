# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from katalon.core.dependencies import (
    CurrentUser,
    DBDep,
    OptionalCurrentUser,
    has_record_permission,
    require_feature,
)
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
    current_user: CurrentUser,
    format: str = Query(...),
    subtype: str | None = Query(None),
) -> StreamingResponse:
    if record_type not in RECORD_TYPES:
        raise HTTPException(status_code=404, detail=f"Unbekannter Typ: {record_type}")

    # A caller without record-read permission on this type (or draft/internal
    # visibility generally) only gets public/published rows — mirrors the
    # list-endpoint convention instead of leaking internal records/status via
    # the bulk dump (#389).
    visibility_user = (
        current_user if await has_record_permission(db, current_user, record_type, "read") else None
    )

    filename = f"{record_type}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    if format == "csv":
        return StreamingResponse(
            export_service.stream_csv(db, record_type, subtype, visibility_user),
            media_type=MEDIA_TYPES["csv"],
            headers=headers,
        )
    if format == "json":
        return StreamingResponse(
            export_service.stream_json(db, record_type, subtype, visibility_user),
            media_type=MEDIA_TYPES["json"],
            headers=headers,
        )

    if record_type not in await mapped_record_types(db, format):
        raise HTTPException(
            status_code=422,
            detail=f"Format '{format}' hat keine Feld-Mappings für Typ '{record_type}'.",
        )
    return StreamingResponse(
        export_service.stream_xml(db, record_type, format, visibility_user),
        media_type=MEDIA_TYPES["xml"],
        headers={"Content-Disposition": f'attachment; filename="{record_type}.{format}.xml"'},
    )


@router.get(
    "/{record_type}/{record_id}",
    summary="Export a single record as JSON-LD, Turtle RDF, or metadata format XML",
)
@router.get(
    "/{record_type}/{record_id}/export",
    summary="Export a single record as JSON-LD, Turtle RDF, or metadata format XML",
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
    norm_type = record_type.lower().strip()
    if norm_type.endswith("s") and norm_type[:-1] in RECORD_TYPES:
        norm_type = norm_type[:-1]

    format_key = (format or "").lower().strip()
    if not format_key or format_key in {"jsonld", "json-ld", "json_ld", "ttl", "turtle", "rdf"}:
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

    if norm_type not in RECORD_TYPES:
        raise HTTPException(status_code=404, detail=f"Unbekannter Typ: {record_type}")

    metadata_format = await metadata_format_service.get_format(format_key)
    if metadata_format is None:
        raise HTTPException(status_code=404, detail=f"Unbekanntes Export-Format '{format_key}'.")

    if norm_type not in await mapped_record_types(db, format_key):
        raise HTTPException(
            status_code=422,
            detail=f"Format '{format_key}' hat keine Feld-Mappings für Typ '{norm_type}'.",
        )

    from katalon.services.export_context_service import build_export_context_from_db

    try:
        ctx = await build_export_context_from_db(db, norm_type, record_id, base_url=str(request.base_url))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    has_perm = await has_record_permission(db, current_user, norm_type, "read") if current_user else False
    if not has_perm and ctx.record.status != "public":
        raise HTTPException(status_code=404, detail=f"{norm_type.capitalize()} nicht gefunden")

    from katalon.integrations.metadata_format import CompiledMappingSet
    from katalon.services import metadata_mapping_service

    mapping_index = await metadata_mapping_service.get_mapping_index(db, format_key)
    record_mappings = mapping_index.get(norm_type)
    if record_mappings is None:
        record_mappings = CompiledMappingSet(format_key=format_key, record_type=norm_type)

    missing = metadata_format.required_field_errors(ctx, record_mappings)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Datensatz kann nicht als {metadata_format.label} exportiert werden: {'; '.join(missing)}.",
        )

    el = metadata_format.render(ctx, record_mappings)
    import xml.etree.ElementTree as ET

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(el, encoding="unicode") + "\n"
    filename = f"{ctx.record.idno or ctx.record.id}.{format_key}.xml"

    return Response(
        content=xml_str,
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
