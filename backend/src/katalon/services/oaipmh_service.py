# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import base64
import json
import logging
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from katalon.config import settings
from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportRecordContext,
    MetadataFormat,
    utc_timestamp,
)
from katalon.services.metadata_mapping_service import MappingIndex
from katalon.services.oai_state_service import DeletedRecord

OAI_NS = "http://www.openarchives.org/OAI/2.0/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = (
    "http://www.openarchives.org/OAI/2.0/ "
    "http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"
)

PAGE_SIZE = 100

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ResumptionToken
# ---------------------------------------------------------------------------

def encode_token(
    offset: int,
    search_after: list[Any] | None,
    set_spec: str | None,
    from_: str | None,
    until: str | None,
    prefix: str,
    *,
    phase: str = "records",
    total: int | None = None,
) -> str:
    """``phase`` "records" pages through live records (search_after = ES sort values),
    "deleted" through deleted records (search_after = [deleted_at, record_id])."""
    data: dict[str, Any] = {"o": offset, "sa": search_after, "s": set_spec, "f": from_, "u": until, "p": prefix}
    if phase != "records":
        data["ph"] = phase
    if total is not None:
        data["t"] = total
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode()


def decode_token(token: str) -> dict[str, Any]:
    data = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
    return {
        "offset": data.get("o", 0),
        "search_after": data.get("sa"),
        "set_spec": data.get("s"),
        "from_": data.get("f"),
        "until": data.get("u"),
        "prefix": data.get("p", "oai_dc"),
        "phase": data.get("ph", "records"),
        "total": data.get("t"),
    }


@dataclass(frozen=True)
class Resumption:
    """resumptionToken of one list page; ``token`` None marks the last page."""

    token: str | None
    complete_list_size: int
    cursor: int


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _root() -> ET.Element:
    el = ET.Element("OAI-PMH", {
        "xmlns": OAI_NS,
        "xmlns:xsi": XSI_NS,
        "xsi:schemaLocation": SCHEMA_LOC,
    })
    ET.SubElement(el, "responseDate").text = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return el


def _error(el: ET.Element, code: str, message: str) -> str:
    err = ET.SubElement(el, "error", code=code)
    err.text = message
    return ET.tostring(el, encoding="unicode", xml_declaration=True)


def _datestamp(ts: str | None) -> str:
    return utc_timestamp(ts) or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Format-agnostic record rendering (delegates to the metadata_format_service registry)
# ---------------------------------------------------------------------------

def _record_errors(
    hit: dict[str, Any],
    metadata_format: MetadataFormat,
    mapping_index: MappingIndex | dict[str, Any] | None,
) -> list[str]:
    ctx = ExportRecordContext.from_hit(hit)
    record_mappings = (mapping_index or {}).get(ctx.record.record_type)
    if record_mappings is None:
        record_mappings = CompiledMappingSet(
            format_key=metadata_format.key, record_type=ctx.record.record_type
        )
    return metadata_format.required_field_errors(ctx, record_mappings)


def _hit_to_oai_record(
    hit: dict[str, Any],
    set_spec: str | None,
    metadata_format: MetadataFormat,
    mapping_index: MappingIndex | dict[str, Any] | None = None,
) -> ET.Element | None:
    """Render one hit, or return None if it's missing required fields for `metadata_format`."""
    ctx = ExportRecordContext.from_hit(hit)
    record_id = ctx.record.id
    record_type = ctx.record.record_type
    record_mappings = (mapping_index or {}).get(record_type)
    if record_mappings is None:
        record_mappings = CompiledMappingSet(format_key=metadata_format.key, record_type=record_type)

    missing = metadata_format.required_field_errors(ctx, record_mappings)
    if missing:
        logger.warning(
            "OAI-PMH %s: Datensatz %s übersprungen (Pflichtfelder fehlen): %s",
            metadata_format.key, ctx.record.idno or record_id, "; ".join(missing),
        )
        return None

    oai_rec = ET.Element("record")
    header = ET.SubElement(oai_rec, "header")
    ET.SubElement(header, "identifier").text = f"oai:{settings.oai_repository_domain}:{record_type}:{record_id}"
    ET.SubElement(header, "datestamp").text = _datestamp(ctx.record.updated_at)
    if set_spec:
        ET.SubElement(header, "setSpec").text = set_spec

    metadata_el = ET.SubElement(oai_rec, "metadata")
    metadata_el.append(metadata_format.render(ctx, record_mappings))
    return oai_rec


def _hit_to_oai_header(hit: dict[str, Any], set_spec: str | None) -> ET.Element:
    src = hit["_source"]
    record_id = hit["_id"]
    record_type = src.get("record_type", "")

    header = ET.Element("header")
    ET.SubElement(header, "identifier").text = f"oai:{settings.oai_repository_domain}:{record_type}:{record_id}"
    ET.SubElement(header, "datestamp").text = _datestamp(src.get("updated_at"))
    if set_spec:
        ET.SubElement(header, "setSpec").text = set_spec
    return header


def _deleted_header(record_type: str, record_id: str, datestamp: str, set_spec: str | None) -> ET.Element:
    header = ET.Element("header", status="deleted")
    ET.SubElement(header, "identifier").text = f"oai:{settings.oai_repository_domain}:{record_type}:{record_id}"
    ET.SubElement(header, "datestamp").text = datestamp
    if set_spec:
        ET.SubElement(header, "setSpec").text = set_spec
    return header


def _deleted_record_header(item: DeletedRecord, set_spec: str | None) -> ET.Element:
    return _deleted_header(
        item.record_type, item.record_id, item.deleted_at.strftime("%Y-%m-%dT%H:%M:%SZ"), set_spec
    )


def _hit_deleted_header(hit: dict[str, Any], set_spec: str | None) -> ET.Element:
    """A live record this format cannot disseminate (e.g. failed rights checks) is reported as
    deleted, so incremental harvesters drop an earlier copy of it."""
    ctx = ExportRecordContext.from_hit(hit)
    return _deleted_header(
        ctx.record.record_type, ctx.record.id, _datestamp(ctx.record.updated_at), set_spec
    )


def _append_resumption(
    parent: ET.Element,
    resumption: Resumption | None,
    hits: list[dict[str, Any]],
    total: int,
    offset: int,
    set_spec: str | None,
    from_: str | None,
    until: str | None,
    prefix: str,
) -> None:
    if resumption is None:
        # Records only (callers without deleted-record support).
        next_offset = offset + len(hits)
        token = (
            encode_token(next_offset, hits[-1].get("sort"), set_spec, from_, until, prefix)
            if hits and next_offset < total
            else None
        )
        resumption = Resumption(token, total, offset)
    if resumption.complete_list_size <= 0 and not resumption.token:
        return
    rt = ET.SubElement(
        parent,
        "resumptionToken",
        completeListSize=str(resumption.complete_list_size),
        cursor=str(resumption.cursor),
    )
    if resumption.token:
        rt.text = resumption.token


# ---------------------------------------------------------------------------
# Verb responses
# ---------------------------------------------------------------------------

def identify(base_url: str, repo_name: str, admin_email: str, earliest: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="Identify")
    req.text = base_url
    ident = ET.SubElement(root, "Identify")
    ET.SubElement(ident, "repositoryName").text = repo_name
    ET.SubElement(ident, "baseURL").text = base_url
    ET.SubElement(ident, "protocolVersion").text = "2.0"
    ET.SubElement(ident, "adminEmail").text = admin_email
    ET.SubElement(ident, "earliestDatestamp").text = earliest
    # Depublished/deleted records are reported, but rows may be lost (e.g. records
    # removed before the tracking table existed), hence "transient".
    ET.SubElement(ident, "deletedRecord").text = "transient"
    ET.SubElement(ident, "granularity").text = "YYYY-MM-DDThh:mm:ssZ"
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def list_metadata_formats(base_url: str, formats: list[MetadataFormat]) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="ListMetadataFormats")
    req.text = base_url
    lmf = ET.SubElement(root, "ListMetadataFormats")
    if not formats:
        return _error(root, "noMetadataFormats", "No metadata formats are mapped yet.")
    for metadata_format in formats:
        fmt = ET.SubElement(lmf, "metadataFormat")
        ET.SubElement(fmt, "metadataPrefix").text = metadata_format.key
        ET.SubElement(fmt, "schema").text = metadata_format.schema_url
        ET.SubElement(fmt, "metadataNamespace").text = metadata_format.namespace
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def list_sets(sets: list[Any], base_url: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="ListSets")
    req.text = base_url
    if not sets:
        return _error(root, "noSetHierarchy", "This repository has no sets defined.")
    ls = ET.SubElement(root, "ListSets")
    for s in sets:
        set_el = ET.SubElement(ls, "set")
        ET.SubElement(set_el, "setSpec").text = s.set_spec
        ET.SubElement(set_el, "setName").text = s.set_name
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _list_page(
    verb: str,
    hits: list[dict[str, Any]],
    total: int,
    offset: int,
    set_spec: str | None,
    from_: str | None,
    until: str | None,
    prefix: str,
    base_url: str,
    metadata_format: MetadataFormat | None,
    mapping_index: MappingIndex | dict[str, Any] | None,
    deleted: Sequence[DeletedRecord],
    resumption: Resumption | None,
) -> str:
    root = _root()
    req_attrs: dict[str, str] = {"verb": verb, "metadataPrefix": prefix}
    if set_spec:
        req_attrs["set"] = set_spec
    if from_:
        req_attrs["from"] = from_
    if until:
        req_attrs["until"] = until
    req = ET.SubElement(root, "request", req_attrs)
    req.text = base_url

    if not hits and not deleted:
        return _error(root, "noRecordsMatch", "No records match the query.")

    container = ET.SubElement(root, verb)
    for hit in hits:
        if verb == "ListRecords":
            assert metadata_format is not None
            el = _hit_to_oai_record(hit, set_spec, metadata_format, mapping_index)
            if el is None:
                el = ET.Element("record")
                el.append(_hit_deleted_header(hit, set_spec))
            container.append(el)
        elif metadata_format is not None and _record_errors(hit, metadata_format, mapping_index):
            container.append(_hit_deleted_header(hit, set_spec))
        else:
            container.append(_hit_to_oai_header(hit, set_spec))
    for item in deleted:
        header = _deleted_record_header(item, set_spec)
        if verb == "ListRecords":
            record = ET.Element("record")
            record.append(header)
            container.append(record)
        else:
            container.append(header)

    _append_resumption(container, resumption, hits, total, offset, set_spec, from_, until, prefix)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def list_records(
    hits: list[dict[str, Any]],
    total: int,
    offset: int,
    set_spec: str | None,
    from_: str | None,
    until: str | None,
    prefix: str,
    base_url: str,
    metadata_format: MetadataFormat,
    mapping_index: MappingIndex | dict[str, Any] | None = None,
    *,
    deleted: Sequence[DeletedRecord] = (),
    resumption: Resumption | None = None,
) -> str:
    return _list_page(
        "ListRecords", hits, total, offset, set_spec, from_, until, prefix, base_url,
        metadata_format, mapping_index, deleted, resumption,
    )


def list_identifiers(
    hits: list[dict[str, Any]],
    total: int,
    offset: int,
    set_spec: str | None,
    from_: str | None,
    until: str | None,
    prefix: str,
    base_url: str,
    metadata_format: MetadataFormat | None = None,
    mapping_index: MappingIndex | dict[str, Any] | None = None,
    *,
    deleted: Sequence[DeletedRecord] = (),
    resumption: Resumption | None = None,
) -> str:
    return _list_page(
        "ListIdentifiers", hits, total, offset, set_spec, from_, until, prefix, base_url,
        metadata_format, mapping_index, deleted, resumption,
    )


def get_record(
    hit: dict[str, Any],
    base_url: str,
    identifier: str,
    prefix: str,
    metadata_format: MetadataFormat,
    mapping_index: MappingIndex | dict[str, Any] | None = None,
) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="GetRecord", metadataPrefix=prefix,
                        identifier=identifier)
    req.text = base_url
    record_el = _hit_to_oai_record(hit, None, metadata_format, mapping_index)
    if record_el is None:
        record_el = ET.Element("record")
        record_el.append(_hit_deleted_header(hit, None))
    gr = ET.SubElement(root, "GetRecord")
    gr.append(record_el)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def get_deleted_record(item: DeletedRecord, base_url: str, identifier: str, prefix: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="GetRecord", metadataPrefix=prefix,
                        identifier=identifier)
    req.text = base_url
    record_el = ET.SubElement(ET.SubElement(root, "GetRecord"), "record")
    record_el.append(_deleted_record_header(item, None))
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def bad_verb(verb: str, base_url: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request")
    req.text = base_url
    return _error(root, "badVerb", f"Illegal OAI verb: {verb!r}")
