from __future__ import annotations

import base64
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

OAI_NS = "http://www.openarchives.org/OAI/2.0/"
DC_NS = "http://purl.org/dc/elements/1.1/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = (
    "http://www.openarchives.org/OAI/2.0/ "
    "http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"
)

PAGE_SIZE = 100


# ---------------------------------------------------------------------------
# ResumptionToken
# ---------------------------------------------------------------------------

def encode_token(offset: int, set_spec: str | None, from_: str | None, until: str | None, prefix: str) -> str:
    data = {"o": offset, "s": set_spec, "f": from_, "u": until, "p": prefix}
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode()


def decode_token(token: str) -> dict[str, Any]:
    data = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
    return {
        "offset": data.get("o", 0),
        "set_spec": data.get("s"),
        "from_": data.get("f"),
        "until": data.get("u"),
        "prefix": data.get("p", "oai_dc"),
    }


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
    if not ts:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ts[:19].replace(" ", "T") + "Z"


# ---------------------------------------------------------------------------
# Dublin Core mapping from ES hit
# ---------------------------------------------------------------------------

def _hit_to_oai_record(hit: dict[str, Any], set_spec: str | None) -> ET.Element:
    src = hit["_source"]
    record_id = hit["_id"]
    record_type = src.get("record_type", "")
    md: dict = src.get("metadata", {})

    oai_rec = ET.Element("record")
    header = ET.SubElement(oai_rec, "header")
    ET.SubElement(header, "identifier").text = f"oai:katalon:{record_type}:{record_id}"
    ET.SubElement(header, "datestamp").text = _datestamp(src.get("updated_at"))
    if set_spec:
        ET.SubElement(header, "setSpec").text = set_spec

    metadata_el = ET.SubElement(oai_rec, "metadata")
    dc = ET.SubElement(metadata_el, "oai_dc:dc", {
        "xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "xmlns:dc": DC_NS,
        "xmlns:xsi": XSI_NS,
        "xsi:schemaLocation": (
            "http://www.openarchives.org/OAI/2.0/oai_dc/ "
            "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
        ),
    })

    title = src.get("title") or record_id
    ET.SubElement(dc, "dc:title").text = str(title)

    for creator_key in ("creator", "photographer", "author", "artist", "illustrator"):
        if val := md.get(creator_key):
            if isinstance(val, list):
                for item in val:
                    text = item.get("value", "") if isinstance(item, dict) else str(item)
                    if text:
                        ET.SubElement(dc, "dc:creator").text = text
            else:
                ET.SubElement(dc, "dc:creator").text = str(val)
            break

    if desc := md.get("description"):
        text = str(desc)
        if isinstance(desc, list):
            text = desc[0].get("value", "") if isinstance(desc[0], dict) else str(desc[0])
        ET.SubElement(dc, "dc:description").text = text

    keywords = md.get("keywords", [])
    if isinstance(keywords, list):
        for kw in keywords:
            if kw:
                ET.SubElement(dc, "dc:subject").text = str(kw)
    elif keywords:
        ET.SubElement(dc, "dc:subject").text = str(keywords)

    date_val = (src.get("created_at") or "")[:10]
    if date_val:
        ET.SubElement(dc, "dc:date").text = date_val

    ET.SubElement(dc, "dc:type").text = record_type
    ET.SubElement(dc, "dc:identifier").text = f"oai:katalon:{record_type}:{record_id}"

    if idno := src.get("idno") or md.get("idno"):
        ET.SubElement(dc, "dc:identifier").text = str(idno)

    if lang := md.get("language"):
        ET.SubElement(dc, "dc:language").text = str(lang)

    for rights_key in ("rights", "license", "licence"):
        if val := md.get(rights_key):
            ET.SubElement(dc, "dc:rights").text = str(val)
            break

    return oai_rec


def _hit_to_oai_header(hit: dict[str, Any], set_spec: str | None) -> ET.Element:
    src = hit["_source"]
    record_id = hit["_id"]
    record_type = src.get("record_type", "")

    header = ET.Element("header")
    ET.SubElement(header, "identifier").text = f"oai:katalon:{record_type}:{record_id}"
    ET.SubElement(header, "datestamp").text = _datestamp(src.get("updated_at"))
    if set_spec:
        ET.SubElement(header, "setSpec").text = set_spec
    return header


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
    ET.SubElement(ident, "deletedRecord").text = "no"
    ET.SubElement(ident, "granularity").text = "YYYY-MM-DDThh:mm:ssZ"
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def list_metadata_formats(base_url: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="ListMetadataFormats")
    req.text = base_url
    lmf = ET.SubElement(root, "ListMetadataFormats")
    fmt = ET.SubElement(lmf, "metadataFormat")
    ET.SubElement(fmt, "metadataPrefix").text = "oai_dc"
    ET.SubElement(fmt, "schema").text = "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
    ET.SubElement(fmt, "metadataNamespace").text = "http://www.openarchives.org/OAI/2.0/oai_dc/"
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


def list_records(
    hits: list[dict],
    total: int,
    offset: int,
    set_spec: str | None,
    from_: str | None,
    until: str | None,
    prefix: str,
    base_url: str,
) -> str:
    root = _root()
    req_attrs: dict[str, str] = {"verb": "ListRecords", "metadataPrefix": prefix}
    if set_spec:
        req_attrs["set"] = set_spec
    if from_:
        req_attrs["from"] = from_
    if until:
        req_attrs["until"] = until
    req = ET.SubElement(root, "request", **req_attrs)
    req.text = base_url

    if not hits:
        return _error(root, "noRecordsMatch", "No records match the query.")

    lr = ET.SubElement(root, "ListRecords")
    for hit in hits:
        lr.append(_hit_to_oai_record(hit, set_spec))

    next_offset = offset + len(hits)
    if next_offset < total:
        token = encode_token(next_offset, set_spec, from_, until, prefix)
        rt = ET.SubElement(lr, "resumptionToken", completeListSize=str(total), cursor=str(offset))
        rt.text = token
    elif total > 0:
        ET.SubElement(lr, "resumptionToken", completeListSize=str(total), cursor=str(offset))

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def list_identifiers(
    hits: list[dict],
    total: int,
    offset: int,
    set_spec: str | None,
    from_: str | None,
    until: str | None,
    prefix: str,
    base_url: str,
) -> str:
    root = _root()
    req_attrs: dict[str, str] = {"verb": "ListIdentifiers", "metadataPrefix": prefix}
    if set_spec:
        req_attrs["set"] = set_spec
    if from_:
        req_attrs["from"] = from_
    if until:
        req_attrs["until"] = until
    req = ET.SubElement(root, "request", **req_attrs)
    req.text = base_url

    if not hits:
        return _error(root, "noRecordsMatch", "No records match the query.")

    li = ET.SubElement(root, "ListIdentifiers")
    for hit in hits:
        li.append(_hit_to_oai_header(hit, set_spec))

    next_offset = offset + len(hits)
    if next_offset < total:
        token = encode_token(next_offset, set_spec, from_, until, prefix)
        rt = ET.SubElement(li, "resumptionToken", completeListSize=str(total), cursor=str(offset))
        rt.text = token
    elif total > 0:
        ET.SubElement(li, "resumptionToken", completeListSize=str(total), cursor=str(offset))

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def get_record(hit: dict[str, Any], base_url: str, identifier: str, prefix: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="GetRecord", metadataPrefix=prefix,
                        identifier=identifier)
    req.text = base_url
    gr = ET.SubElement(root, "GetRecord")
    gr.append(_hit_to_oai_record(hit, None))
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def bad_verb(verb: str, base_url: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request")
    req.text = base_url
    return _error(root, "badVerb", f"Illegal OAI verb: {verb!r}")
