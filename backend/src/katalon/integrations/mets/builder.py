# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportRecordContext,
    MappingSpec,
    SourceKind,
    append_path,
)
from katalon.services.metadata_mapping_service import extract_values

METS_NS = "http://www.loc.gov/METS/"
MODS_NS = "http://www.loc.gov/mods/v3"
DV_NS = "http://dfg-viewer.de/"
XLINK_NS = "http://www.w3.org/1999/xlink"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = "http://www.loc.gov/METS/ http://www.loc.gov/standards/mets/mets.xsd http://www.loc.gov/mods/v3 http://www.loc.gov/standards/mods/v3/mods-3-8.xsd"

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
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(val))).strip())


def _rule_values(ctx: ExportRecordContext, rule: MappingSpec) -> list[str]:
    values: list[Any] = []
    if rule.source_kind == SourceKind.FIELD and rule.field_name:
        values = extract_values(ctx, rule.field_name)
        if not values and rule.field_name in ctx.fields:
            values = [_extract_display_value(ctx.fields[rule.field_name])]
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
                    values.append(val)
    elif rule.source_kind == SourceKind.RECORD:
        prop = rule.source_config.get("property") or rule.target_key
        if prop == "canonical_url" and ctx.record.canonical_url:
            values = [ctx.record.canonical_url]
        elif getattr(ctx.record, prop, None):
            values = [str(getattr(ctx.record, prop))]
    elif rule.source_kind == SourceKind.CONSTANT:
        if const_val := rule.source_config.get("value") or rule.settings.get("value"):
            values = [str(const_val)]
    elif rule.source_kind == SourceKind.MEDIA:
        prop = rule.source_config.get("property", "url")
        for m in ctx.media:
            val = getattr(m, prop, None)
            if val:
                values.append(str(val))

    cleaned = [_clean_text(v) for v in values if v is not None]
    return [c for c in cleaned if c]


def build_mets_element(
    ctx: ExportRecordContext,
    mapping_set: CompiledMappingSet,
    institution_config: dict[str, Any] | None = None,
) -> ET.Element:
    """Build a complete METS container wrapping descriptive MODS and administrative rights metadata."""
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

    for rule in mapping_set.rules:
        if not rule.is_enabled:
            continue
        vals = _rule_values(ctx, rule)
        if not vals:
            continue

        prefix = rule.settings.get("prefix", "")
        for raw_val in vals:
            val = f"{prefix}{raw_val}" if prefix else raw_val

            if rule.target_key == "mods:titleInfo/mods:title":
                t_info = ET.SubElement(mods, "mods:titleInfo")
                ET.SubElement(t_info, "mods:title").text = val
            elif rule.target_key == "mods:name/mods:namePart":
                name_el = ET.SubElement(mods, "mods:name")
                ET.SubElement(name_el, "mods:namePart").text = val
                role = _clean_text(rule.settings.get("role") or rule.source_config.get("role"))
                if role:
                    role_el = ET.SubElement(name_el, "mods:role")
                    ET.SubElement(role_el, "mods:roleTerm", {"type": "text"}).text = role
            elif rule.target_key == "mods:accessCondition":
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
                append_path(mods, rule.target_key, val)

    # Resolve license for amdSec and mods:mods fallback
    if not license_values:
        for m in ctx.media:
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

    # 3. Administrative metadata section (amdSec) - two rightsMD sections
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

    # 4. Media files section (fileSec) if record has media
    file_ids: list[str] = []
    if ctx.media:
        file_sec = ET.SubElement(mets, "mets:fileSec")
        file_grp = ET.SubElement(file_sec, "mets:fileGrp", {"USE": "DEFAULT"})
        for i, m in enumerate(ctx.media, start=1):
            fid = f"FILE_{i:04d}"
            file_ids.append(fid)
            f_attribs = {"ID": fid, "MIMETYPE": m.mime_type}
            file_el = ET.SubElement(file_grp, "mets:file", f_attribs)
            loc_attribs = {"LOCTYPE": "URL", "xlink:href": m.url}
            if m.filename:
                loc_attribs["xlink:title"] = m.filename
            ET.SubElement(file_el, "mets:FLocat", loc_attribs)

    # 5. Flat structural map (structMap) for 1 record
    struct_map = ET.SubElement(mets, "mets:structMap", {"TYPE": "LOGICAL"})
    div_attribs = {
        "ID": "LOG_0001",
        "TYPE": record_type,
        "DMDID": "DMD_0001",
        "ADMID": "AMD_0001",
        "LABEL": str(title),
    }
    div = ET.SubElement(struct_map, "mets:div", div_attribs)
    for fid in file_ids:
        ET.SubElement(div, "mets:fptr", {"FILEID": fid})

    return mets
