from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy import select

from katalon.core.dependencies import DBDep
from katalon.core.models import Object, Entity, Place, Occurrence
from katalon.services import oaipmh_service

router = APIRouter(prefix="/oai", tags=["oai-pmh"])

_MODEL_MAP = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
}


@router.get("")
async def oai_endpoint(request: Request, db: DBDep) -> Response:
    params = dict(request.query_params)
    verb = params.get("verb", "")
    base_url = str(request.url).split("?")[0]

    if verb == "Identify":
        xml = oaipmh_service.identify(base_url)

    elif verb == "ListSets":
        xml = oaipmh_service.list_sets()

    elif verb == "ListRecords":
        prefix = params.get("metadataPrefix", "oai_dc")
        if prefix != "oai_dc":
            root = oaipmh_service._root()
            xml = oaipmh_service._error(root, "cannotDisseminateFormat", f"Unsupported prefix: {prefix}")
        else:
            set_spec = params.get("set", "object")
            model = _MODEL_MAP.get(set_spec, Object)
            result = await db.execute(select(model).limit(100))
            records = list(result.scalars().all())
            xml = oaipmh_service.list_records(records, set_spec, base_url)

    elif verb == "GetRecord":
        identifier = params.get("identifier", "")
        parts = identifier.split(":")
        if len(parts) >= 4:
            record_type = parts[2]
            record_id = parts[3]
            model = _MODEL_MAP.get(record_type)
            if model:
                from uuid import UUID
                try:
                    uid = UUID(record_id)
                    result = await db.execute(select(model).where(model.id == uid))
                    rec = result.scalar_one_or_none()
                    if rec:
                        xml = oaipmh_service.get_record(rec, record_type, base_url)
                    else:
                        root = oaipmh_service._root()
                        xml = oaipmh_service._error(root, "idDoesNotExist", f"No record: {identifier}")
                except (ValueError, Exception):
                    root = oaipmh_service._root()
                    xml = oaipmh_service._error(root, "idDoesNotExist", "Invalid identifier format")
            else:
                root = oaipmh_service._root()
                xml = oaipmh_service._error(root, "idDoesNotExist", "Unknown record type")
        else:
            root = oaipmh_service._root()
            xml = oaipmh_service._error(root, "idDoesNotExist", "Malformed identifier")

    elif verb == "ListMetadataFormats":
        from xml.etree.ElementTree import Element, SubElement, tostring
        root = oaipmh_service._root()
        lmf = SubElement(root, "ListMetadataFormats")
        fmt = SubElement(lmf, "metadataFormat")
        SubElement(fmt, "metadataPrefix").text = "oai_dc"
        SubElement(fmt, "schema").text = "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
        SubElement(fmt, "metadataNamespace").text = "http://www.openarchives.org/OAI/2.0/oai_dc/"
        xml = tostring(root, encoding="unicode", xml_declaration=True)

    else:
        xml = oaipmh_service.bad_verb(verb)

    return Response(content=xml, media_type="application/xml")
