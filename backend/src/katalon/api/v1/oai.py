# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import logging
from typing import Any, cast

from elasticsearch import ConnectionError, ConnectionTimeout, NotFoundError, TransportError
from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy import select

from katalon.api.v1.portal import resolve_lang_text
from katalon.config import settings
from katalon.core.dependencies import DBDep
from katalon.core.limiter import limiter
from katalon.core.models import OAISet, PortalConfig
from katalon.core.visibility import PUBLIC_STATUSES
from katalon.services import metadata_format_service, oai_state_service, oaipmh_service
from katalon.services.export_context_service import expand_omitted_contexts
from katalon.services.metadata_mapping_service import (
    get_mapping_index,
    mapped_format_keys,
    mapped_record_types,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oai", tags=["oai-pmh"])

PAGE_SIZE = 100


async def _available_formats(db: DBDep) -> dict[str, Any]:
    """Formats that are both registered and actually mapped to at least one field."""
    mapped_keys = await mapped_format_keys(db)
    formats = await metadata_format_service.list_formats()
    return {fmt.key: fmt for fmt in formats if fmt.key in mapped_keys}

def _normalize_prefix(prefix: str, available: dict[str, Any]) -> str:
    if prefix in ("jsonld", "json-ld") and "json_ld" in available:
        return "json_ld"
    return prefix


async def _es_search_for_oai(
    set_def: OAISet | None,
    from_param: str | None,
    until_param: str | None,
    search_after: list[Any] | None,
    identifier: str | None = None,
    record_types: set[str] | None = None,
) -> dict[str, Any]:
    """Run an Elasticsearch query for OAI-PMH harvesting.

    Uses `search_after` (not `from`) to page — resumption tokens are
    inherently sequential, so there is no result-window depth ceiling for
    harvesting arbitrarily large repositories.
    """
    from katalon.integrations.elasticsearch import INDEX_NAME, get_es

    es = get_es()
    filters: list[dict[str, Any]] = []

    if identifier:
        # GetRecord: fetch by exact ES _id, then enforce public status
        try:
            result = await es.get(index=INDEX_NAME, id=identifier)
        except NotFoundError:
            return {"hits": {"hits": [], "total": {"value": 0}}, "aggregations": {}}
        if result.get("found") and result.get("_source", {}).get("status") in PUBLIC_STATUSES:
            return {"hits": {"hits": [result], "total": {"value": 1}}, "aggregations": {}}
        return {"hits": {"hits": [], "total": {"value": 0}}, "aggregations": {}}

    # Always restrict OAI-PMH to public records
    filters.append({"terms": {"status": list(PUBLIC_STATUSES)}})

    if record_types:
        filters.append({"terms": {"record_type": sorted(record_types)}})

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
        must: list[dict[str, Any]] = [{"multi_match": {
            "query": set_def.filter_q,
            "fields": ["title^3", "search_text^2"],
            "type": "best_fields",
            "lenient": True,
        }}]
    else:
        must = [{"match_all": {}}]

    query = {"bool": {"must": must, "filter": filters}}
    body: dict[str, Any] = {
        "query": query,
        "sort": [{"updated_at": "asc"}, {"_doc": "asc"}],
        "size": PAGE_SIZE,
        "track_total_hits": True,
    }
    if search_after:
        body["search_after"] = search_after
    result = await es.search(index=INDEX_NAME, body=body)
    return cast(dict[str, Any], result.body)


def _deletions_apply(set_def: OAISet | None, record_types: set[str]) -> set[str]:
    """Record types whose deletions belong to this request.

    A deleted record has no metadata left, so sets that filter by metadata,
    status or free text cannot tell whether it belonged to them; such sets
    report no deletions.
    """
    if set_def is None:
        return record_types
    if set_def.filter_metadata or set_def.filter_q or set_def.filter_status:
        return set()
    if set_def.filter_record_type:
        return record_types & {set_def.filter_record_type}
    return record_types


async def _harvest_page(
    db: DBDep,
    set_def: OAISet | None,
    set_spec: str | None,
    from_: str | None,
    until: str | None,
    prefix: str,
    record_types: set[str],
    token: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[oai_state_service.DeletedRecord], oaipmh_service.Resumption]:
    """One page of ListRecords/ListIdentifiers: live records first, then deletions."""
    offset = token["offset"] if token else 0
    phase = token["phase"] if token else "records"
    deletion_types = _deletions_apply(set_def, record_types)
    hits: list[dict[str, Any]] = []

    if phase == "records":
        es_result = await _es_search_for_oai(
            set_def, from_, until, token["search_after"] if token else None, record_types=record_types
        )
        hits = es_result.get("hits", {}).get("hits", [])
        live_total = es_result.get("hits", {}).get("total", {}).get("value", 0)
        deleted_total = await oai_state_service.count_deleted(db, deletion_types, from_, until)
        total = live_total + deleted_total
        next_offset = offset + len(hits)
        if hits and next_offset < live_total:
            records_token = oaipmh_service.encode_token(
                next_offset, hits[-1].get("sort"), set_spec, from_, until, prefix, total=total
            )
            return hits, [], oaipmh_service.Resumption(records_token, total, offset)
        if not hits and deleted_total:
            phase = "deleted"  # no live records (left): continue with deletions on this page
        elif deleted_total:
            switch_token = oaipmh_service.encode_token(
                next_offset, None, set_spec, from_, until, prefix, phase="deleted", total=total
            )
            return hits, [], oaipmh_service.Resumption(switch_token, total, offset)
        else:
            return hits, [], oaipmh_service.Resumption(None, total, offset)
    else:
        total = int(token.get("total") or 0) if token else 0

    after = token["search_after"] if token and token["phase"] == "deleted" else None
    rows = await oai_state_service.deleted_page(
        db, deletion_types, from_, until, after, PAGE_SIZE + 1
    )
    page, more = rows[:PAGE_SIZE], len(rows) > PAGE_SIZE
    if not total:
        total = offset + len(page) + (1 if more else 0)
    next_token: str | None = None
    if more:
        last = page[-1]
        next_token = oaipmh_service.encode_token(
            offset + len(page), [last.deleted_at.isoformat(), last.record_id],
            set_spec, from_, until, prefix, phase="deleted", total=total,
        )
    return hits, page, oaipmh_service.Resumption(next_token, total, offset)


@router.get(
    "",
    summary="Handle OAI-PMH protocol requests (Identify, ListRecords, GetRecord, etc.)",
)
@limiter.limit(lambda: settings.rate_limit_oai)
async def oai_endpoint(request: Request, db: DBDep) -> Response:
    params = dict(request.query_params)
    verb = params.get("verb", "")
    base_url = str(request.url).split("?")[0]

    try:
        # --- Identify ---
        if verb == "Identify":
            config_res = await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
            config = config_res.scalar_one_or_none()
            repo_name = (resolve_lang_text(config.site_title) if config else "") or "Katalon"
            admin_email = getattr(settings, "oai_admin_email", settings.default_admin_email)
            earliest = "2024-01-01T00:00:00Z"
            xml = oaipmh_service.identify(base_url, repo_name, admin_email, earliest)

        # --- ListMetadataFormats ---
        elif verb == "ListMetadataFormats":
            available = await _available_formats(db)
            xml = oaipmh_service.list_metadata_formats(base_url, list(available.values()))

        # --- ListSets ---
        elif verb == "ListSets":
            result = await db.execute(select(OAISet).order_by(OAISet.set_spec))
            sets = list(result.scalars().all())
            xml = oaipmh_service.list_sets(sets, base_url)

        # --- ListRecords ---
        elif verb == "ListRecords":
            available = await _available_formats(db)
            raw_prefix = params.get("metadataPrefix", next(iter(available), "oai_dc"))
            prefix = _normalize_prefix(raw_prefix, available)

            token_str = params.get("resumptionToken")
            token_data: dict[str, Any] | None = None
            if token_str:
                token_data = oaipmh_service.decode_token(token_str)
                offset = token_data["offset"]
                set_spec = token_data["set_spec"]
                from_ = token_data["from_"]
                until = token_data["until"]
                prefix = token_data["prefix"]
            else:
                offset = 0
                set_spec = params.get("set")
                from_ = params.get("from")
                until = params.get("until")

            if prefix not in available:
                root = oaipmh_service._root()
                xml = oaipmh_service._error(
                    root, "cannotDisseminateFormat", f"Unsupported prefix: {prefix}"
                )
                return Response(content=xml, media_type="application/xml")

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

            record_types = await mapped_record_types(db, prefix)
            hits, deleted, resumption = await _harvest_page(
                db, set_def, set_spec, from_, until, prefix, record_types, token_data
            )
            mapping_index = await get_mapping_index(db, prefix)
            await expand_omitted_contexts(db, hits)
            xml = oaipmh_service.list_records(
                hits, resumption.complete_list_size, offset, set_spec, from_, until, prefix, base_url,
                available[prefix], mapping_index, deleted=deleted, resumption=resumption,
            )

        # --- ListIdentifiers ---
        elif verb == "ListIdentifiers":
            available = await _available_formats(db)
            raw_prefix = params.get("metadataPrefix", next(iter(available), "oai_dc"))
            prefix = _normalize_prefix(raw_prefix, available)

            token_str = params.get("resumptionToken")
            token_data = None
            if token_str:
                token_data = oaipmh_service.decode_token(token_str)
                offset = token_data["offset"]
                set_spec = token_data["set_spec"]
                from_ = token_data["from_"]
                until = token_data["until"]
                prefix = token_data["prefix"]
            else:
                offset = 0
                set_spec = params.get("set")
                from_ = params.get("from")
                until = params.get("until")

            if prefix not in available:
                root = oaipmh_service._root()
                xml = oaipmh_service._error(
                    root, "cannotDisseminateFormat", f"Unsupported prefix: {prefix}"
                )
                return Response(content=xml, media_type="application/xml")

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

            record_types = await mapped_record_types(db, prefix)
            hits, deleted, resumption = await _harvest_page(
                db, set_def, set_spec, from_, until, prefix, record_types, token_data
            )
            mapping_index = await get_mapping_index(db, prefix)
            await expand_omitted_contexts(db, hits)
            xml = oaipmh_service.list_identifiers(
                hits, resumption.complete_list_size, offset, set_spec, from_, until, prefix, base_url,
                available[prefix], mapping_index, deleted=deleted, resumption=resumption,
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
            available = await _available_formats(db)
            raw_prefix = params.get("metadataPrefix", next(iter(available), "oai_dc"))
            prefix = _normalize_prefix(raw_prefix, available)
            if prefix not in available:
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
            es_result = await _es_search_for_oai(None, None, None, None, identifier=record_id)

            hits = es_result.get("hits", {}).get("hits", [])
            mapped_types = await mapped_record_types(db, prefix)
            gone = (
                await oai_state_service.get_deleted(db, parts[2], record_id)
                if parts[2] in mapped_types
                else None
            )
            if gone is not None and (not hits or hits[0]["_source"].get("record_type") != parts[2]):
                xml = oaipmh_service.get_deleted_record(gone, base_url, identifier, prefix)
            elif not hits or hits[0]["_source"].get("record_type") not in mapped_types:
                root = oaipmh_service._root()
                xml = oaipmh_service._error(root, "idDoesNotExist", f"No record: {identifier}")
            else:
                mapping_index = await get_mapping_index(db, prefix)
                await expand_omitted_contexts(db, hits[:1])
                xml = oaipmh_service.get_record(
                    hits[0], base_url, identifier, prefix, available[prefix], mapping_index
                )

        else:
            xml = oaipmh_service.bad_verb(verb, base_url)

    except (ConnectionError, ConnectionTimeout, TransportError) as exc:
        logger.error("OAI-PMH request failed due to ES error: %s", exc)
        return Response(
            content="Search backend temporarily unavailable. Please retry later.",
            status_code=503,
            headers={"Retry-After": "60"},
        )

    return Response(content=xml, media_type="application/xml")
