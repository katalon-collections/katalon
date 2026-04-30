from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any


OAI_NS = "http://www.openarchives.org/OAI/2.0/"
DC_NS = "http://purl.org/dc/elements/1.1/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = (
    "http://www.openarchives.org/OAI/2.0/ "
    "http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"
)

REPOSITORY_NAME = "Katalon MMS"
BASE_URL = "http://localhost:8000/v1/oai"
ADMIN_EMAIL = "admin@example.org"
EARLIEST_DATESTAMP = "2024-01-01T00:00:00Z"
DELETED_RECORD = "no"
GRANULARITY = "YYYY-MM-DDThh:mm:ssZ"


def _root() -> ET.Element:
    el = ET.Element("OAI-PMH", {
        "xmlns": OAI_NS,
        "xmlns:xsi": XSI_NS,
        "xsi:schemaLocation": SCHEMA_LOC,
    })
    ET.SubElement(el, "responseDate").text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return el


def _error(el: ET.Element, code: str, message: str) -> str:
    err = ET.SubElement(el, "error", code=code)
    err.text = message
    return ET.tostring(el, encoding="unicode", xml_declaration=True)


def identify(base_url: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="Identify")
    req.text = base_url
    ident = ET.SubElement(root, "Identify")
    ET.SubElement(ident, "repositoryName").text = REPOSITORY_NAME
    ET.SubElement(ident, "baseURL").text = base_url
    ET.SubElement(ident, "protocolVersion").text = "2.0"
    ET.SubElement(ident, "adminEmail").text = ADMIN_EMAIL
    ET.SubElement(ident, "earliestDatestamp").text = EARLIEST_DATESTAMP
    ET.SubElement(ident, "deletedRecord").text = DELETED_RECORD
    ET.SubElement(ident, "granularity").text = GRANULARITY
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _record_to_dc(record: Any, record_type: str) -> ET.Element:
    oai_rec = ET.Element("record")
    header = ET.SubElement(oai_rec, "header")
    ET.SubElement(header, "identifier").text = f"oai:katalon:{record_type}:{record.id}"
    ET.SubElement(header, "datestamp").text = record.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    ET.SubElement(header, "setSpec").text = record_type

    metadata_el = ET.SubElement(oai_rec, "metadata")
    dc = ET.SubElement(metadata_el, "oai_dc:dc", {
        "xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "xmlns:dc": DC_NS,
        "xmlns:xsi": XSI_NS,
        "xsi:schemaLocation": "http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
    })

    md: dict = record.metadata_ or {}
    title = md.get("title", [{}])
    title_val = title[0].get("value", "") if isinstance(title, list) and title else str(title)
    ET.SubElement(dc, "dc:title").text = title_val or str(record.id)
    ET.SubElement(dc, "dc:type").text = record_type
    ET.SubElement(dc, "dc:identifier").text = str(record.id)
    if hasattr(record, "idno") and record.idno:
        ET.SubElement(dc, "dc:identifier").text = record.idno
    ET.SubElement(dc, "dc:date").text = record.created_at.strftime("%Y-%m-%d")

    return oai_rec


def list_records(records: list[Any], record_type: str, base_url: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="ListRecords", metadataPrefix="oai_dc")
    req.text = base_url
    if not records:
        return _error(root, "noRecordsMatch", "No records found")
    lr = ET.SubElement(root, "ListRecords")
    for rec in records:
        lr.append(_record_to_dc(rec, record_type))
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def get_record(record: Any, record_type: str, base_url: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="GetRecord", metadataPrefix="oai_dc",
                        identifier=f"oai:katalon:{record_type}:{record.id}")
    req.text = base_url
    gr = ET.SubElement(root, "GetRecord")
    gr.append(_record_to_dc(record, record_type))
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def list_sets() -> str:
    root = _root()
    ls = ET.SubElement(root, "ListSets")
    for s in ["object", "entity", "place", "occurrence"]:
        set_el = ET.SubElement(ls, "set")
        ET.SubElement(set_el, "setSpec").text = s
        ET.SubElement(set_el, "setName").text = s.capitalize() + "s"
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def bad_verb(verb: str) -> str:
    root = _root()
    return _error(root, "badVerb", f"Illegal OAI verb: {verb}")
