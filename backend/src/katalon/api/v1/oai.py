from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy import select

from katalon.config import settings
from katalon.core.dependencies import DBDep
from katalon.core.limiter import limiter
from katalon.core.models import OAISet, PortalConfig
from katalon.services import oaipmh_service
from katalon.services.metadata_mapping_service import OAI_DC_FORMAT, get_mapping_index

router = APIRouter(prefix="/oai", tags=["oai-pmh"])

PAGE_SIZE = 100


async def _es_search_for_oai(
    set_def: OAISet | None,
    from_param: str | None,
    until_param: str | None,
    offset: int,
    identifier: str | None = None,
) -> dict[str, Any]:
    """Run an Elasticsearch query for OAI-PMH harvesting."""
    from katalon.integrations.elasticsearch import INDEX_NAME, get_es

    es = get_es()
    filters: list[dict] = []

    if identifier:
        # GetRecord: fetch by exact ES _id
        result = await es.get(index=INDEX_NAME, id=identifier, ignore=[404])
        if result.get("found"):
            return {"hits": {"hits": [result], "total": {"value": 1}}, "aggregations": {}}
        return {"hits": {"hits": [], "total": {"value": 0}}, "aggregations": {}}

    if set_def:
        if set_def.filter_record_type:
            filters.append({"term": {"record_type": set_def.filter_record_type}})
        if set_def.filter_status:
            filters.append({"term": {"status": set_def.filter_status}})
        for field, value in (set_def.filter_metadata or {}).items():
            filters.append({"term": {f"metadata.{field}.keyword": str(value)}})

    if from_param or until_param:
        date_range: dict[str, str] = {}
        if from_param:
            date_range["gte"] = from_param
        if until_param:
            date_range["lte"] = until_param
        filters.append({"range": {"updated_at": date_range}})

    if set_def and set_def.filter_q:
        must: list[dict] = [{"multi_match": {
            "query": set_def.filter_q,
            "fields": ["title^3", "search_text^2"],
            "type": "best_fields",
            "lenient": True,
        }}]
    else:
        must = [{"match_all": {}}]

    query = {"bool": {"must": must, "filter": filters}}
    body = {
        "query": query,
        "sort": [{"updated_at": "asc"}, {"_doc": "asc"}],
        "from": offset,
        "size": PAGE_SIZE,
    }
    result = await es.search(index=INDEX_NAME, body=body)
    return result.body


@router.get("")
@limiter.limit("100/minute")
async def oai_endpoint(request: Request, db: DBDep) -> Response:
    params = dict(request.query_params)
    verb = params.get("verb", "")
    base_url = str(request.url).split("?")[0]

    # --- Identify ---
    if verb == "Identify":
        config_res = await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
        config = config_res.scalar_one_or_none()
        repo_name = config.site_title if config else "Katalon"
        admin_email = getattr(settings, "oai_admin_email", settings.default_admin_email)
        earliest = "2024-01-01T00:00:00Z"
        xml = oaipmh_service.identify(base_url, repo_name, admin_email, earliest)

    # --- ListMetadataFormats ---
    elif verb == "ListMetadataFormats":
        xml = oaipmh_service.list_metadata_formats(base_url)

    # --- ListSets ---
    elif verb == "ListSets":
        result = await db.execute(select(OAISet).order_by(OAISet.set_spec))
        sets = list(result.scalars().all())
        xml = oaipmh_service.list_sets(sets, base_url)

    # --- ListRecords ---
    elif verb == "ListRecords":
        prefix = params.get("metadataPrefix", "oai_dc")

        token_str = params.get("resumptionToken")
        if token_str:
            token = oaipmh_service.decode_token(token_str)
            offset = token["offset"]
            set_spec = token["set_spec"]
            from_ = token["from_"]
            until = token["until"]
            prefix = token["prefix"]
        else:
            if prefix != "oai_dc":
                root = oaipmh_service._root()
                msg = f"Unsupported prefix: {prefix}"
                xml = oaipmh_service._error(
                    root, "cannotDisseminateFormat", msg
                )
                return Response(content=xml, media_type="application/xml")
            offset = 0
            set_spec = params.get("set")
            from_ = params.get("from")
            until = params.get("until")

        set_def: OAISet | None = None
        if set_spec:
            res = await db.execute(
                select(OAISet).where(OAISet.set_spec == set_spec)
            )
            set_def = res.scalar_one_or_none()
            if not set_def:
                root = oaipmh_service._root()
                xml = oaipmh_service._error(
                    root, "noSetHierarchy", f"Unknown set: {set_spec}"
                )
                return Response(content=xml, media_type="application/xml")

        es_result = await _es_search_for_oai(set_def, from_, until, offset)

        hits = es_result.get("hits", {}).get("hits", [])
        total = es_result.get("hits", {}).get("total", {}).get("value", 0)
        mapping_index = await get_mapping_index(db, OAI_DC_FORMAT)
        xml = oaipmh_service.list_records(
            hits, total, offset, set_spec, from_, until, prefix, base_url, mapping_index
        )

    # --- ListIdentifiers ---
    elif verb == "ListIdentifiers":
        prefix = params.get("metadataPrefix", "oai_dc")

        token_str = params.get("resumptionToken")
        if token_str:
            token = oaipmh_service.decode_token(token_str)
            offset = token["offset"]
            set_spec = token["set_spec"]
            from_ = token["from_"]
            until = token["until"]
            prefix = token["prefix"]
        else:
            if prefix != "oai_dc":
                root = oaipmh_service._root()
                msg = f"Unsupported prefix: {prefix}"
                xml = oaipmh_service._error(
                    root, "cannotDisseminateFormat", msg
                )
                return Response(content=xml, media_type="application/xml")
            offset = 0
            set_spec = params.get("set")
            from_ = params.get("from")
            until = params.get("until")

        set_def = None
        if set_spec:
            res = await db.execute(
                select(OAISet).where(OAISet.set_spec == set_spec)
            )
            set_def = res.scalar_one_or_none()
            if not set_def:
                root = oaipmh_service._root()
                xml = oaipmh_service._error(
                    root, "noSetHierarchy", f"Unknown set: {set_spec}"
                )
                return Response(content=xml, media_type="application/xml")

        es_result = await _es_search_for_oai(set_def, from_, until, offset)

        hits = es_result.get("hits", {}).get("hits", [])
        total = es_result.get("hits", {}).get("total", {}).get("value", 0)
        xml = oaipmh_service.list_identifiers(
            hits, total, offset, set_spec, from_, until, prefix, base_url
        )

    # --- GetRecord ---
    elif verb == "GetRecord":
        if params.get("resumptionToken"):
            root = oaipmh_service._root()
            xml = oaipmh_service._error(
                root, "badResumptionToken",
                "GetRecord does not support resumptionToken."
            )
            return Response(content=xml, media_type="application/xml")

        identifier = params.get("identifier", "")
        prefix = params.get("metadataPrefix", "oai_dc")
        if prefix != "oai_dc":
            root = oaipmh_service._root()
            msg = f"Unsupported prefix: {prefix}"
            xml = oaipmh_service._error(
                root, "cannotDisseminateFormat", msg
            )
            return Response(content=xml, media_type="application/xml")

        parts = identifier.split(":")
        if len(parts) < 4:
            root = oaipmh_service._root()
            xml = oaipmh_service._error(root, "idDoesNotExist", "Malformed identifier.")
            return Response(content=xml, media_type="application/xml")

        record_id = parts[3]
        es_result = await _es_search_for_oai(None, None, None, 0, identifier=record_id)

        hits = es_result.get("hits", {}).get("hits", [])
        if not hits:
            root = oaipmh_service._root()
            xml = oaipmh_service._error(root, "idDoesNotExist", f"No record: {identifier}")
        else:
            mapping_index = await get_mapping_index(db, OAI_DC_FORMAT)
            xml = oaipmh_service.get_record(hits[0], base_url, identifier, prefix, mapping_index)

    else:
        xml = oaipmh_service.bad_verb(verb, base_url)

    return Response(content=xml, media_type="application/xml")
