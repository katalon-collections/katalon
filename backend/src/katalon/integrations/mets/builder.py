# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

from katalon.integrations.lido.builder import (
    _authority_ids,
    _id_fields,
    date_limits,
    format_date_display,
)
from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportMediaItem,
    ExportRecordContext,
    ExportRelation,
    MappingSpec,
    SourceKind,
    plain_text,
)
from katalon.services.metadata_mapping_service import extract_values

METS_NS = "http://www.loc.gov/METS/"
MODS_NS = "http://www.loc.gov/mods/v3"
DV_NS = "http://dfg-viewer.de/"
XLINK_NS = "http://www.w3.org/1999/xlink"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = "http://www.loc.gov/METS/ http://www.loc.gov/standards/mets/mets.xsd http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-8.xsd"

MARC_RELATORS = "http://id.loc.gov/vocabulary/relators"

# actor_types (shared with LIDO: person/corporation/family) -> mods:name/@type
NAME_TYPES = {
    "person": "personal",
    "personal": "personal",
    "corporation": "corporate",
    "corporate": "corporate",
    "family": "family",
    "conference": "conference",
}
# Top-level MODS elements that describe one thing per record: values of several rules
# go into one element instead of one element per value.
MERGED_CONTAINERS = frozenset({"mods:originInfo", "mods:physicalDescription", "mods:recordInfo"})
DATE_TARGETS = frozenset({"mods:originInfo/mods:dateCreated"})

ET.register_namespace("mets", METS_NS)
ET.register_namespace("mods", MODS_NS)
ET.register_namespace("dv", DV_NS)
ET.register_namespace("xlink", XLINK_NS)
ET.register_namespace("xsi", XSI_NS)


def _extract_display_value(val: Any) -> Any:
    """Pull a human-readable scalar out of vocabulary and group values."""
    if isinstance(val, dict):
        if val.get("uri"):
            return val["uri"]
        if "label" in val:
            return _extract_display_value(val["label"])
        if "de" in val or "en" in val:
            return val.get("de") or val.get("en")
        for value in val.values():
            if (extracted := _extract_display_value(value)) is not None:
                return extracted
        return None
    if isinstance(val, list):
        return next((extracted for item in val if (extracted := _extract_display_value(item)) is not None), None)
    return val


def _clean_text(val: Any) -> str:
    if val is None:
        return ""
    if (val := _extract_display_value(val)) is None:
        return ""
    return plain_text(str(val))


def _rule_hits(ctx: ExportRecordContext, rule: MappingSpec) -> list[tuple[str, ExportRelation | None]]:
    """Cleaned values of a rule, with the relation each came from (None for non-relations)."""
    hits: list[tuple[Any, ExportRelation | None]] = []
    if rule.source_kind == SourceKind.FIELD and rule.field_name:
        values = extract_values(ctx, rule.field_name)
        if not values and rule.field_name in ctx.fields:
            values = [_extract_display_value(ctx.fields[rule.field_name])]
        hits = [(v, None) for v in values]
    elif rule.source_kind == SourceKind.RELATION:
        rel_type = rule.source_config.get("relation_type")
        target_field = rule.source_config.get("target_field")
        rel_direction = str(rule.source_config.get("direction") or "outbound")
        for rel in ctx.relations:
            if rel.direction != rel_direction:
                continue
            if not rel_type or rel.relation_type == rel_type:
                val = (
                    rel.target_values.get(target_field)
                    if target_field
                    else (rel.target_label or rel.target_idno)
                )
                if val:
                    hits.append((val, rel))
    elif rule.source_kind == SourceKind.RECORD:
        prop = rule.source_config.get("property") or rule.target_key
        if prop == "canonical_url" and ctx.record.canonical_url:
            hits = [(ctx.record.canonical_url, None)]
        elif getattr(ctx.record, prop, None):
            hits = [(str(getattr(ctx.record, prop)), None)]
    elif rule.source_kind == SourceKind.CONSTANT:
        if const_val := rule.source_config.get("value") or rule.settings.get("value"):
            hits = [(str(const_val), None)]
    elif rule.source_kind == SourceKind.MEDIA:
        prop = rule.source_config.get("property", "url")
        for m in ctx.media:
            val = getattr(m, prop, None)
            if val:
                hits.append((str(val), None))

    cleaned = [(_clean_text(v), rel) for v, rel in hits if v is not None]
    result = [(text, rel) for text, rel in cleaned if text]
    # settings.limit: keep only the first N values (e.g. one licence per record).
    limit = rule.settings.get("limit")
    if isinstance(limit, int) and limit > 0:
        result = result[:limit]
    return result


def _rule_values(ctx: ExportRecordContext, rule: MappingSpec) -> list[str]:
    return [text for text, _rel in _rule_hits(ctx, rule)]


def _container(mods: ET.Element, tag: str) -> ET.Element:
    if tag in MERGED_CONTAINERS:
        for child in mods:
            if child.tag == tag:
                return child
    return ET.SubElement(mods, tag)


def _append(mods: ET.Element, path: str, value: str, attrs: dict[str, str] | None = None) -> None:
    parts = path.split("/")
    el = _container(mods, parts[0]) if len(parts) > 1 else mods
    for part in parts[1:-1]:
        el = ET.SubElement(el, part)
    ET.SubElement(el, parts[-1], attrs or {}).text = value


def _qualifier(part: str) -> str | None:
    if part.endswith("~?") or part.endswith("~"):
        return "approximate"
    if part.endswith("?"):
        return "questionable"
    return None


def _render_date(mods: ET.Element, target_key: str, value: str) -> None:
    """EDTF-lite value -> ISO 8601 date(s) with point/qualifier plus a readable displayDate.

    Free text that is not EDTF-lite only becomes mods:displayDate (ISO elements must hold ISO).
    """
    origin = _container(mods, "mods:originInfo")
    tag = target_key.rsplit("/", 1)[-1]
    limits = date_limits(value)
    if limits is None:
        ET.SubElement(origin, "mods:displayDate").text = value
        return
    start, end = limits
    raw_start, _, raw_end = value.partition("/")
    if "/" not in value:
        attrs = {"encoding": "iso8601", "keyDate": "yes"}
        if qualifier := _qualifier(value):
            attrs["qualifier"] = qualifier
        ET.SubElement(origin, tag, attrs).text = start
    else:
        key_set = False
        for point, iso, raw in (("start", start, raw_start), ("end", end, raw_end)):
            if not iso:
                continue
            attrs = {"encoding": "iso8601", "point": point}
            if not key_set:
                attrs["keyDate"] = "yes"
                key_set = True
            if qualifier := _qualifier(raw):
                attrs["qualifier"] = qualifier
            ET.SubElement(origin, tag, attrs).text = iso
    ET.SubElement(origin, "mods:displayDate").text = format_date_display(value)


def _render_name(
    mods: ET.Element,
    text: str,
    rel: ExportRelation | None,
    rule: MappingSpec,
    config: dict[str, Any],
) -> None:
    attrs: dict[str, str] = {}
    actor_types = config.get("actor_types") or {}
    kind = actor_types.get(rel.target_subtype) if rel and rel.target_subtype else None
    if name_type := NAME_TYPES.get(str(rule.settings.get("name_type") or kind or "")):
        attrs["type"] = name_type
    if rel:
        ids = _authority_ids(rel.target_values, _id_fields(rule, config, "actor_id_fields"))
        if ids:
            attrs["valueURI"] = ids[0][0]
    name_el = ET.SubElement(mods, "mods:name", attrs)
    ET.SubElement(name_el, "mods:namePart").text = text
    ET.SubElement(name_el, "mods:displayForm").text = text
    role = _clean_text(rule.settings.get("role") or rule.source_config.get("role"))
    role_code = _clean_text(rule.settings.get("role_code"))
    if role or role_code:
        role_el = ET.SubElement(name_el, "mods:role")
        if role_code:
            ET.SubElement(
                role_el,
                "mods:roleTerm",
                {
                    "type": "code",
                    "authority": "marcrelator",
                    "authorityURI": MARC_RELATORS,
                    "valueURI": f"{MARC_RELATORS}/{role_code}",
                },
            ).text = role_code
        if role:
            ET.SubElement(role_el, "mods:roleTerm", {"type": "text"}).text = role


def _file_versions(media: ExportMediaItem) -> list[tuple[str, str, str]]:
    """(fileGrp USE, URL, MIME type) per image; IIIF images get a full and a thumbnail JPEG."""
    if media.iiif_base:
        return [
            ("DEFAULT", f"{media.iiif_base}/full/max/0/default.jpg", "image/jpeg"),
            ("THUMBS", f"{media.iiif_base}/full/!400,400/0/default.jpg", "image/jpeg"),
        ]
    return [("DEFAULT", media.url, media.mime_type)]


def build_mets_element(
    ctx: ExportRecordContext,
    mapping_set: CompiledMappingSet,
    institution_config: dict[str, Any] | None = None,
) -> ET.Element:
    """Build a METS container following the DFG-Viewer METS profile: descriptive MODS,
    rights and links in amdSec, files, logical and physical structMap, structLink."""
    inst_cfg = institution_config or mapping_set.institution_config or {}
    record_id = ctx.record.id
    idno = ctx.record.idno or record_id
    record_type = ctx.record.record_type
    title = ctx.record.title or idno

    institution_name = str(inst_cfg.get("institution_name") or inst_cfg.get("repository_name") or "Katalon").strip()
    website = str(inst_cfg.get("website") or inst_cfg.get("repository_url") or "").strip()

    # METS Root
    mets = ET.Element(
        "mets:mets",
        {
            "xmlns:mets": METS_NS,
            "xmlns:mods": MODS_NS,
            "xmlns:dv": DV_NS,
            "xmlns:xlink": XLINK_NS,
            "xmlns:xsi": XSI_NS,
            "xsi:schemaLocation": SCHEMA_LOC,
            "OBJID": str(idno),
            "TYPE": record_type,
        },
    )

    # 1. METS Header (metsHdr)
    hdr = ET.SubElement(mets, "mets:metsHdr", {"CREATEDATE": datetime.now(UTC).isoformat()})
    agent = ET.SubElement(hdr, "mets:agent", {"ROLE": "CREATOR", "TYPE": "ORGANIZATION"})
    ET.SubElement(agent, "mets:name").text = institution_name

    # 2. Descriptive metadata section (dmdSec) wrapping MODS
    dmd = ET.SubElement(mets, "mets:dmdSec", {"ID": "DMD_0001"})
    md_wrap = ET.SubElement(dmd, "mets:mdWrap", {"MDTYPE": "MODS", "MIMETYPE": "text/xml"})
    xml_data = ET.SubElement(md_wrap, "mets:xmlData")
    mods = ET.SubElement(xml_data, "mods:mods", {"ID": f"MODS_{record_id}"})

    # Collect values by target
    license_values: list[str] = []
    # Elements MODS allows once per record (dates without point, record identifier):
    # the first value wins, later ones would only be dropped by consumers.
    single_done: set[str] = set()

    for rule in mapping_set.rules:
        if not rule.is_enabled:
            continue
        hits = _rule_hits(ctx, rule)
        if not hits:
            continue

        prefix = rule.settings.get("prefix", "")
        for raw_val, rel in hits:
            val = f"{prefix}{raw_val}" if prefix else raw_val

            if rule.target_key == "mods:titleInfo/mods:title":
                t_info = ET.SubElement(mods, "mods:titleInfo")
                ET.SubElement(t_info, "mods:title").text = val
            elif rule.target_key == "mods:name/mods:namePart":
                _render_name(mods, val, rel, rule, inst_cfg)
            elif rule.target_key in DATE_TARGETS:
                if rule.target_key not in single_done:
                    single_done.add(rule.target_key)
                    _render_date(mods, rule.target_key, val)
            elif rule.target_key == "mods:recordInfo/mods:recordIdentifier":
                if rule.target_key not in single_done:
                    single_done.add(rule.target_key)
                    source = _clean_text(rule.settings.get("source"))
                    _append(mods, rule.target_key, val, {"source": source} if source else None)
            elif rule.target_key == "mods:originInfo/mods:place/mods:placeTerm":
                place = ET.SubElement(_container(mods, "mods:originInfo"), "mods:place")
                ET.SubElement(place, "mods:placeTerm", {"type": "text"}).text = val
            elif rule.target_key == "mods:relatedItem/mods:titleInfo/mods:title":
                rel_type = _clean_text(rule.settings.get("type"))
                related = ET.SubElement(mods, "mods:relatedItem", {"type": rel_type} if rel_type else {})
                ET.SubElement(ET.SubElement(related, "mods:titleInfo"), "mods:title").text = val
            elif rule.target_key == "mods:accessCondition":
                if val in license_values:
                    continue
                license_values.append(val)
                attribs = {"type": "use and reproduction"}
                if val.startswith("http://") or val.startswith("https://"):
                    attribs["xlink:href"] = val
                acc = ET.SubElement(mods, "mods:accessCondition", attribs)
                acc.text = val
            elif rule.target_key == "mods:note" or rule.target_key.startswith("mods:note/"):
                note_type = _clean_text(rule.settings.get("type") or rule.source_config.get("type"))
                attribs = {"type": note_type} if note_type else {}
                note_el = ET.SubElement(mods, "mods:note", attribs)
                note_el.text = val
            else:
                _append(mods, rule.target_key, val)

    media = [m for m in ctx.media if m.is_public]

    # Resolve license for amdSec and mods:mods fallback
    if not license_values:
        for m in media:
            if m.license_uri:
                license_values.append(m.license_uri)
                break
    if not license_values and inst_cfg.get("record_rights"):
        license_values.append(str(inst_cfg["record_rights"]))
    if not license_values:
        license_values.append("https://creativecommons.org/publicdomain/zero/1.0/")

    primary_license = license_values[0]

    # Ensure mods:mods has mods:accessCondition if not already added by an explicit rule
    has_mods_access = any(
        el.tag == "mods:accessCondition" or el.tag.endswith("}accessCondition")
        for el in mods
    )
    if not has_mods_access:
        for lic in license_values:
            attribs = {"type": "use and reproduction"}
            if lic.startswith("http://") or lic.startswith("https://"):
                attribs["xlink:href"] = lic
            acc = ET.SubElement(mods, "mods:accessCondition", attribs)
            acc.text = lic

    # 3. Administrative metadata section (amdSec): two rightsMD sections, digiprovMD links
    amd = ET.SubElement(mets, "mets:amdSec", {"ID": "AMD_0001"})

    # Section 1: MODS accessCondition inside rightsMD
    rights_mods = ET.SubElement(amd, "mets:rightsMD", {"ID": "RIGHTS_MODS_0001"})
    wrap_mods = ET.SubElement(rights_mods, "mets:mdWrap", {"MDTYPE": "MODS", "MIMETYPE": "text/xml"})
    data_mods = ET.SubElement(wrap_mods, "mets:xmlData")
    for lic in license_values:
        attribs = {"type": "use and reproduction"}
        if lic.startswith("http://") or lic.startswith("https://"):
            attribs["xlink:href"] = lic
        r_acc = ET.SubElement(data_mods, "mods:accessCondition", attribs)
        r_acc.text = lic

    # Section 2: DFG-Viewer dv:rights inside rightsMD
    rights_dv = ET.SubElement(amd, "mets:rightsMD", {"ID": "RIGHTS_DVRIGHTS_0001"})
    wrap_dv = ET.SubElement(rights_dv, "mets:mdWrap", {"MDTYPE": "OTHER", "OTHERMDTYPE": "DVRIGHTS", "MIMETYPE": "text/xml"})
    data_dv = ET.SubElement(wrap_dv, "mets:xmlData")
    dv_rights = ET.SubElement(data_dv, "dv:rights")
    ET.SubElement(dv_rights, "dv:owner").text = institution_name
    if website:
        ET.SubElement(dv_rights, "dv:ownerSiteURL").text = website
    ET.SubElement(dv_rights, "dv:license").text = primary_license

    # Section 3: dv:links to the record's public page (reference and presentation)
    if ctx.record.canonical_url:
        digiprov = ET.SubElement(amd, "mets:digiprovMD", {"ID": "DIGIPROV_0001"})
        wrap_links = ET.SubElement(
            digiprov, "mets:mdWrap", {"MDTYPE": "OTHER", "OTHERMDTYPE": "DVLINKS", "MIMETYPE": "text/xml"}
        )
        dv_links = ET.SubElement(ET.SubElement(wrap_links, "mets:xmlData"), "dv:links")
        ET.SubElement(dv_links, "dv:reference").text = ctx.record.canonical_url
        ET.SubElement(dv_links, "dv:presentation").text = ctx.record.canonical_url

    # 4. Media files section (fileSec): public media only, one file per version
    pages: list[list[str]] = []
    if media:
        file_sec = ET.SubElement(mets, "mets:fileSec")
        groups: dict[str, ET.Element] = {}
        versions = [_file_versions(m) for m in media]
        for use in ("DEFAULT", "THUMBS"):
            if any(v[0] == use for item in versions for v in item):
                groups[use] = ET.SubElement(file_sec, "mets:fileGrp", {"USE": use})
        for i, (m, item_versions) in enumerate(zip(media, versions, strict=True), start=1):
            page_files: list[str] = []
            for use, url, mime in item_versions:
                fid = f"FILE_{i:04d}" if use == "DEFAULT" else f"FILE_{i:04d}_{use}"
                page_files.append(fid)
                file_el = ET.SubElement(groups[use], "mets:file", {"ID": fid, "MIMETYPE": mime})
                loc_attribs = {"LOCTYPE": "URL", "xlink:href": url}
                if m.filename:
                    loc_attribs["xlink:title"] = m.filename
                ET.SubElement(file_el, "mets:FLocat", loc_attribs)
            pages.append(page_files)

    # 5. Logical structMap: one div for the record; TYPE from the DFG-Viewer structure set
    # when configured (mets_logical_type), else the record type.
    struct_map = ET.SubElement(mets, "mets:structMap", {"TYPE": "LOGICAL"})
    div_attribs = {
        "ID": "LOG_0001",
        "TYPE": str(inst_cfg.get("mets_logical_type") or record_type),
        "DMDID": "DMD_0001",
        "ADMID": "AMD_0001",
        "LABEL": str(title),
    }
    ET.SubElement(struct_map, "mets:div", div_attribs)

    # 6. Physical structMap (one page per image) and structLink to the logical div
    if pages:
        physical = ET.SubElement(mets, "mets:structMap", {"TYPE": "PHYSICAL"})
        sequence = ET.SubElement(physical, "mets:div", {"ID": "PHYS_0000", "TYPE": "physSequence"})
        struct_link = ET.Element("mets:structLink")
        ET.SubElement(struct_link, "mets:smLink", {"xlink:from": "LOG_0001", "xlink:to": "PHYS_0000"})
        for i, page_files in enumerate(pages, start=1):
            page_id = f"PHYS_{i:04d}"
            page = ET.SubElement(sequence, "mets:div", {"ID": page_id, "TYPE": "page", "ORDER": str(i)})
            for fid in page_files:
                ET.SubElement(page, "mets:fptr", {"FILEID": fid})
            ET.SubElement(struct_link, "mets:smLink", {"xlink:from": "LOG_0001", "xlink:to": page_id})
        mets.append(struct_link)

    return mets
