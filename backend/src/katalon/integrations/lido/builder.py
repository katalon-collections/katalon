# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportRecordContext,
    SourceKind,
    append_path,
)
from katalon.services.metadata_mapping_service import extract_values

LIDO_NS = "http://www.lido-schema.org"
GML_NS = "http://www.opengis.net/gml"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = "http://www.lido-schema.org http://www.lido-schema.org/schema/v1.0/lido-v1.0.xsd"


def _extract_display_value(val: Any) -> Any:
    """Pull a human-readable scalar out of vocab/group field value shapes.

    Group and vocab-typed fields serialize as dicts like
    {"id": ..., "label": "CC0 1.0", "uri": "..."}, single-key group wrappers
    like {"rechtemodell": {...}}, localized label dicts ({"de": ..., "en": ...}),
    or lists thereof. Without this, such values leak their Python repr
    (e.g. "[{'rechtemodell': {...}}]") straight into rendered XML text.
    """
    if isinstance(val, dict):
        if val.get("uri"):
            return val["uri"]
        if "label" in val:
            return _extract_display_value(val["label"])
        if "de" in val or "en" in val:
            return val.get("de") or val.get("en")
        for v in val.values():
            if (extracted := _extract_display_value(v)) is not None:
                return extracted
        return None
    if isinstance(val, list):
        for item in val:
            if (extracted := _extract_display_value(item)) is not None:
                return extracted
        return None
    return val


def _clean_text(val: Any) -> str:
    """Strip HTML tags and unescape entities for clean XML text."""
    if val is None:
        return ""
    val = _extract_display_value(val)
    if val is None:
        return ""
    text = str(val)
    # Remove HTML tags if present
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return html.unescape(text)


def _format_iso_date(val: Any) -> str | None:
    """Normalize date string to ISO-8601 (YYYY, YYYY-MM, or YYYY-MM-DD)."""
    if not val:
        return None
    s = str(val).strip()
    # Match YYYY-MM-DD
    if m := re.match(r"^(\d{4})-(\d{2})-(\d{2})", s):
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Match DD-MM-YYYY or DD.MM.YYYY -> convert to YYYY-MM-DD
    if m := re.match(r"^(\d{2})[-.](\d{2})[-.](\d{4})", s):
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # Match YYYY
    if m := re.match(r"^(\d{4})", s):
        return m.group(1)
    return s


def build_lido_element(
    ctx: ExportRecordContext,
    mapping_set: CompiledMappingSet,
    institution_config: dict[str, Any] | None = None,
) -> ET.Element:
    """Build a complete, schema-valid LIDO 1.0 <lido:lidoWrap> element."""
    inst_cfg = institution_config or {}
    isil = inst_cfg.get("isil", "DE-3066")
    repo_name = inst_cfg.get("repository_name", "Historische Bildpostkarten - Universität Osnabrück")
    repo_url = inst_cfg.get("repository_url", "https://bildpostkarten.uni-osnabrueck.de")
    repo_location = inst_cfg.get("repository_location", "Osnabrück")
    metadata_rights = inst_cfg.get("metadata_rights_uri", "http://creativecommons.org/publicdomain/zero/1.0/")

    idno = ctx.record.idno or ctx.record.id
    lido_rec_id = f"{isil}--{idno}" if isil else idno

    wrap = ET.Element("lido:lidoWrap", {
        "xmlns:lido": LIDO_NS,
        "xmlns:gml": GML_NS,
        "xmlns:xsi": XSI_NS,
        "xsi:schemaLocation": SCHEMA_LOC,
    })

    lido_el = ET.SubElement(wrap, "lido:lido")

    # 1. lidoRecID (required)
    rec_id_el = ET.SubElement(lido_el, "lido:lidoRecID", {
        "lido:type": "http://terminology.lido-schema.org/lido00100",
    })
    rec_id_el.text = lido_rec_id

    # 2. category (required by LIDO 1.0)
    cat_el = ET.SubElement(lido_el, "lido:category")
    cat_cid = ET.SubElement(cat_el, "lido:conceptID", {
        "lido:type": "http://terminology.lido-schema.org/lido00099",
        "lido:source": "CIDOC CRM",
    })
    cat_cid.text = "http://www.cidoc-crm.org/cidoc-crm/E22_Human-Made_Object"
    cat_term = ET.SubElement(cat_el, "lido:term", {"xml:lang": "de"})
    cat_term.text = "Kulturgut"

    # Index rules by target_key
    rules_by_target = mapping_set.by_target()

    # Helper to get mapped values
    def get_values(target_key: str) -> list[str]:
        res: list[str] = []
        for rule in rules_by_target.get(target_key, []):
            if not rule.is_enabled:
                continue
            if rule.source_kind == SourceKind.FIELD and rule.field_name:
                vals = extract_values(ctx, rule.field_name)
                for v in vals:
                    if prefix := rule.settings.get("prefix"):
                        v = f"{prefix}{v}"
                    res.append(_clean_text(v))
            elif rule.source_kind == SourceKind.CONSTANT:
                val = rule.source_config.get("value") or rule.settings.get("value")
                if val:
                    res.append(_clean_text(val))
            elif rule.source_kind == SourceKind.RECORD:
                prop = rule.source_config.get("property") or "canonical_url"
                val = getattr(ctx.record, prop, None)
                if val:
                    res.append(_clean_text(val))
        return [r for r in res if r]

    # 3. descriptiveMetadata
    desc_meta = ET.SubElement(lido_el, "lido:descriptiveMetadata", {"xml:lang": "de"})

    # 3a. objectClassificationWrap
    class_wrap = ET.SubElement(desc_meta, "lido:objectClassificationWrap")
    work_type_wrap = ET.SubElement(class_wrap, "lido:objectWorkTypeWrap")
    work_type_el = ET.SubElement(work_type_wrap, "lido:objectWorkType")

    # Mapped or fallback object work type
    work_type_vals = get_values("lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType")
    work_type_str = work_type_vals[0] if work_type_vals else (ctx.record.target_subtype or "Postkarte")

    wt_cid_aat = ET.SubElement(work_type_el, "lido:conceptID", {
        "lido:type": "http://terminology.lido-schema.org/lido00099",
        "lido:source": "AAT",
    })
    wt_cid_aat.text = "http://vocab.getty.edu/aat/300026816"
    wt_term_en = ET.SubElement(work_type_el, "lido:term", {"lido:pref": "alternative", "xml:lang": "en"})
    wt_term_en.text = "postcards"
    wt_term_de = ET.SubElement(work_type_el, "lido:term", {"lido:pref": "preferred", "xml:lang": "de"})
    wt_term_de.text = work_type_str

    if ctx.record.target_subtype:
        card_type_el = ET.SubElement(work_type_wrap, "lido:objectWorkType", {"lido:type": "Kartentypus"})
        ET.SubElement(card_type_el, "lido:term").text = _clean_text(ctx.record.target_subtype)

    # Classification wrap (collection name)
    coll_vals = get_values("lido:objectClassificationWrap/lido:classificationWrap/lido:classification")
    if coll_vals or "collection_name" in ctx.fields:
        cwrap = ET.SubElement(class_wrap, "lido:classificationWrap")
        c_el = ET.SubElement(cwrap, "lido:classification", {"lido:type": "Sammlung"})
        c_term = ET.SubElement(c_el, "lido:term")
        c_term.text = coll_vals[0] if coll_vals else _clean_text(ctx.fields.get("collection_name", "Historische Bildpostkarten"))

    # 3b. objectIdentificationWrap
    ident_wrap = ET.SubElement(desc_meta, "lido:objectIdentificationWrap")

    # Title
    title_wrap = ET.SubElement(ident_wrap, "lido:titleWrap")
    title_set = ET.SubElement(title_wrap, "lido:titleSet")
    title_val_el = ET.SubElement(title_set, "lido:appellationValue", {"lido:pref": "preferred"})
    mapped_titles = get_values("lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue")
    title_val_el.text = mapped_titles[0] if mapped_titles else _clean_text(ctx.record.title or idno)

    # Inscriptions
    inscriptions_vals = get_values("lido:objectIdentificationWrap/lido:inscriptionsWrap/lido:inscriptions/lido:inscriptionTranscription")
    if not inscriptions_vals and "inscriptions" in ctx.fields:
        inscriptions_vals = [_clean_text(ctx.fields["inscriptions"])]
    if inscriptions_vals:
        insc_wrap = ET.SubElement(ident_wrap, "lido:inscriptionsWrap")
        for insc in inscriptions_vals:
            insc_el = ET.SubElement(insc_wrap, "lido:inscriptions")
            ET.SubElement(insc_el, "lido:inscriptionTranscription").text = insc

    # Repository
    repo_wrap = ET.SubElement(ident_wrap, "lido:repositoryWrap")
    repo_set = ET.SubElement(repo_wrap, "lido:repositorySet", {"lido:type": "current"})
    repo_name_el = ET.SubElement(repo_set, "lido:repositoryName")
    if isil:
        leg_body_id = ET.SubElement(repo_name_el, "lido:legalBodyID", {
            "lido:type": "http://terminology.lido-schema.org/lido00100",
            "lido:source": "ISIL",
        })
        leg_body_id.text = f"https://sigel.staatsbibliothek-berlin.de/suche?isil={isil}"
    leg_name = ET.SubElement(repo_name_el, "lido:legalBodyName")
    ET.SubElement(leg_name, "lido:appellationValue").text = repo_name
    if repo_url:
        ET.SubElement(repo_name_el, "lido:legalBodyWeblink").text = repo_url

    ET.SubElement(repo_set, "lido:workID", {"lido:type": "Objekt-Signatur"}).text = idno

    if repo_location:
        repo_loc = ET.SubElement(repo_set, "lido:repositoryLocation")
        loc_name = ET.SubElement(repo_loc, "lido:namePlaceSet")
        ET.SubElement(loc_name, "lido:appellationValue").text = repo_location

    # Description
    desc_vals = get_values("lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue")
    if not desc_vals and "description" in ctx.fields:
        desc_vals = [_clean_text(ctx.fields["description"])]
    if desc_vals:
        obj_desc_wrap = ET.SubElement(ident_wrap, "lido:objectDescriptionWrap")
        for d in desc_vals:
            dset = ET.SubElement(obj_desc_wrap, "lido:objectDescriptionSet", {"lido:type": "Beschreibung"})
            ET.SubElement(dset, "lido:descriptiveNoteValue").text = d

    # Measurements
    meas_vals = get_values("lido:objectIdentificationWrap/lido:objectMeasurementsWrap/lido:objectMeasurementsSet/lido:displayObjectMeasurements")
    if not meas_vals and "measurements" in ctx.fields:
        meas_vals = [_clean_text(ctx.fields["measurements"])]
    if meas_vals:
        meas_wrap = ET.SubElement(ident_wrap, "lido:objectMeasurementsWrap")
        for m in meas_vals:
            mset = ET.SubElement(meas_wrap, "lido:objectMeasurementsSet")
            ET.SubElement(mset, "lido:displayObjectMeasurements").text = m

    # 3c. eventWrap
    event_wrap = ET.SubElement(desc_meta, "lido:eventWrap")

    # Helper to find relations by types
    def find_relations(*rel_types: str) -> list[Any]:
        return [r for r in ctx.relations if r.relation_type in rel_types]

    # --- Event 1: Herstellung (Production) ---
    publishers = find_relations("publisher", "verlag", "hersteller")
    pub_places = find_relations("place_of_publication", "verlagsort", "herstellungsort")
    if publishers or pub_places:
        eset = ET.SubElement(event_wrap, "lido:eventSet")
        event = ET.SubElement(eset, "lido:event")
        etype = ET.SubElement(event, "lido:eventType")
        ET.SubElement(etype, "lido:conceptID", {
            "lido:type": "http://terminology.lido-schema.org/lido00099",
            "lido:source": "LIDO Terminologie",
        }).text = "http://terminology.lido-schema.org/lido00007"
        ET.SubElement(etype, "lido:term").text = "Herstellung"

        for pub in publishers:
            eactor = ET.SubElement(event, "lido:eventActor")
            air = ET.SubElement(eactor, "lido:actorInRole")
            act = ET.SubElement(air, "lido:actor")
            nset = ET.SubElement(act, "lido:nameActorSet")
            ET.SubElement(nset, "lido:appellationValue").text = pub.target_label or pub.target_idno or "Unbekannt"
            role = ET.SubElement(air, "lido:roleActor")
            ET.SubElement(role, "lido:term").text = str(pub.metadata.get("role") or "Verlag, Herausgeber")

        for pl in pub_places:
            eplace = ET.SubElement(event, "lido:eventPlace")
            pname = pl.target_label or pl.target_idno or ""
            ET.SubElement(eplace, "lido:displayPlace").text = pname
            place_el = ET.SubElement(eplace, "lido:place")
            if pl.target_idno and "geonames" in pl.target_idno:
                ET.SubElement(place_el, "lido:placeID", {
                    "lido:type": "http://terminology.lido-schema.org/lido00099",
                    "lido:source": "Geonames",
                }).text = pl.target_idno
            pnset = ET.SubElement(place_el, "lido:namePlaceSet")
            ET.SubElement(pnset, "lido:appellationValue").text = pname

        # Materials & Tech
        mat_wrap = ET.SubElement(event, "lido:eventMaterialsTech")
        mtech = ET.SubElement(mat_wrap, "lido:materialsTech")
        tmat = ET.SubElement(mtech, "lido:termMaterialsTech", {"lido:type": "Material"})
        ET.SubElement(tmat, "lido:term").text = _clean_text(ctx.fields.get("material", "Karton"))

    # --- Event 2: Geistige Schöpfung (Creation) ---
    actor_target_key = (
        "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole"
        "/lido:actor/lido:nameActorSet/lido:appellationValue"
    )
    actor_rules = [
        r
        for r in rules_by_target.get(actor_target_key, [])
        if r.is_enabled and r.source_kind == SourceKind.RELATION and r.source_config.get("relation_type")
    ]
    configured_rel_types = [str(r.source_config["relation_type"]) for r in actor_rules]
    role_by_reltype = {
        str(r.source_config["relation_type"]): str(role)
        for r in actor_rules
        if (role := r.settings.get("role") or r.source_config.get("role"))
    }
    creators = (
        find_relations(*configured_rel_types)
        if configured_rel_types
        else find_relations("creator", "photographer", "fotograf", "kuenstler", "artist", "author")
    )
    if creators:
        eset = ET.SubElement(event_wrap, "lido:eventSet")
        event = ET.SubElement(eset, "lido:event")
        etype = ET.SubElement(event, "lido:eventType")
        ET.SubElement(etype, "lido:conceptID", {
            "lido:type": "http://terminology.lido-schema.org/lido00099",
            "lido:source": "LIDO Terminologie",
        }).text = "http://terminology.lido-schema.org/lido00012"
        ET.SubElement(etype, "lido:term").text = "Geistige Schöpfung"

        for cr in creators:
            eactor = ET.SubElement(event, "lido:eventActor")
            air = ET.SubElement(eactor, "lido:actorInRole")
            act = ET.SubElement(air, "lido:actor")
            if gnd := (cr.target_values.get("gnd_id") or (cr.target_idno if cr.target_idno and "gnd" in cr.target_idno.lower() else None)):
                ET.SubElement(act, "lido:actorID", {
                    "lido:type": "http://terminology.lido-schema.org/lido00099",
                    "lido:source": "GND",
                }).text = str(gnd)
            nset = ET.SubElement(act, "lido:nameActorSet")
            ET.SubElement(nset, "lido:appellationValue").text = cr.target_label or cr.target_idno or "Unbekannt"
            role_val = role_by_reltype.get(cr.relation_type) or cr.metadata.get("role")
            if role_val:
                role = ET.SubElement(air, "lido:roleActor")
                ET.SubElement(role, "lido:term").text = str(role_val)

    # --- Event 3: Gebrauch (Use) ---
    usage_date = ctx.fields.get("usage_date") or get_values("lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate")
    if usage_date:
        eset = ET.SubElement(event_wrap, "lido:eventSet")
        event = ET.SubElement(eset, "lido:event")
        etype = ET.SubElement(event, "lido:eventType")
        ET.SubElement(etype, "lido:conceptID", {
            "lido:type": "http://terminology.lido-schema.org/lido00099",
            "lido:source": "LIDO Terminologie",
        }).text = "http://terminology.lido-schema.org/lido00011"
        ET.SubElement(etype, "lido:term").text = "Gebrauch"

        edate = ET.SubElement(event, "lido:eventDate")
        u_str = usage_date[0] if isinstance(usage_date, list) else str(usage_date)
        ET.SubElement(edate, "lido:displayDate", {"lido:label": "Datierung"}).text = _clean_text(u_str)

        earliest = _format_iso_date(ctx.fields.get("usage_date_earliest"))
        latest = _format_iso_date(ctx.fields.get("usage_date_latest"))
        if earliest or latest:
            date_el = ET.SubElement(edate, "lido:date")
            if earliest:
                ET.SubElement(date_el, "lido:earliestDate").text = earliest
            if latest:
                ET.SubElement(date_el, "lido:latestDate").text = latest

    # If no event was created, emit a default minimal creation event for schema validity
    if len(event_wrap) == 0:
        eset = ET.SubElement(event_wrap, "lido:eventSet")
        event = ET.SubElement(eset, "lido:event")
        etype = ET.SubElement(event, "lido:eventType")
        ET.SubElement(etype, "lido:term").text = "Herstellung"

    # 3d. objectRelationWrap (Subjects / Keywords)
    subjects: list[str] = []
    if "subjects" in ctx.fields and isinstance(ctx.fields["subjects"], list):
        subjects.extend(_clean_text(s) for s in ctx.fields["subjects"])
    elif "keywords" in ctx.fields and isinstance(ctx.fields["keywords"], list):
        subjects.extend(_clean_text(s) for s in ctx.fields["keywords"])
    for mapped_subj in get_values("lido:objectRelationWrap/lido:subjectWrap/lido:subjectSet/lido:subject/lido:subjectConcept/lido:term"):
        subjects.append(mapped_subj)

    if subjects:
        rel_wrap = ET.SubElement(desc_meta, "lido:objectRelationWrap")
        subj_wrap = ET.SubElement(rel_wrap, "lido:subjectWrap")
        for subj in subjects:
            sset = ET.SubElement(subj_wrap, "lido:subjectSet")
            s_el = ET.SubElement(sset, "lido:subject")
            s_conc = ET.SubElement(s_el, "lido:subjectConcept")
            ET.SubElement(s_conc, "lido:term").text = subj

    # 4. administrativeMetadata
    admin_meta = ET.SubElement(lido_el, "lido:administrativeMetadata", {"xml:lang": "de"})

    # 4a. rightsWorkWrap
    rwork_wrap = ET.SubElement(admin_meta, "lido:rightsWorkWrap")
    rwork_set = ET.SubElement(rwork_wrap, "lido:rightsWorkSet")
    # License on work (rightsType must precede rightsHolder in LIDO schema)
    license_val = ctx.fields.get("rights") or "http://rightsstatements.org/vocab/InC/1.0/"
    rtype = ET.SubElement(rwork_set, "lido:rightsType")
    ET.SubElement(rtype, "lido:conceptID", {
        "lido:type": "http://terminology.lido-schema.org/lido00099",
        "lido:source": "URI",
    }).text = _clean_text(license_val)

    r_holder = ET.SubElement(rwork_set, "lido:rightsHolder")
    if isil:
        ET.SubElement(r_holder, "lido:legalBodyID", {
            "lido:type": "http://terminology.lido-schema.org/lido00099",
            "lido:source": "ISIL",
        }).text = f"https://sigel.staatsbibliothek-berlin.de/suche?isil={isil}"
    rh_name = ET.SubElement(r_holder, "lido:legalBodyName")
    ET.SubElement(rh_name, "lido:appellationValue").text = repo_name
    if repo_url:
        ET.SubElement(r_holder, "lido:legalBodyWeblink").text = repo_url

    # 4b. recordWrap
    rec_wrap = ET.SubElement(admin_meta, "lido:recordWrap")
    ET.SubElement(rec_wrap, "lido:recordID", {
        "lido:type": "http://terminology.lido-schema.org/lido00099",
    }).text = idno

    rec_type_el = ET.SubElement(rec_wrap, "lido:recordType")
    ET.SubElement(rec_type_el, "lido:conceptID", {
        "lido:type": "http://terminology.lido-schema.org/lido00099",
        "lido:source": "LIDO Terminologie",
    }).text = "http://terminology.lido-schema.org/lido00141"
    ET.SubElement(rec_type_el, "lido:term").text = "Einzelobjekt"

    rec_source = ET.SubElement(rec_wrap, "lido:recordSource")
    if isil:
        ET.SubElement(rec_source, "lido:legalBodyID", {
            "lido:type": "http://terminology.lido-schema.org/lido00099",
            "lido:source": "ISIL",
        }).text = f"https://sigel.staatsbibliothek-berlin.de/suche?isil={isil}"
    rs_name = ET.SubElement(rec_source, "lido:legalBodyName")
    ET.SubElement(rs_name, "lido:appellationValue").text = repo_name
    if repo_url:
        ET.SubElement(rec_source, "lido:legalBodyWeblink").text = repo_url

    # Record Rights (metadata license)
    rec_rights = ET.SubElement(rec_wrap, "lido:recordRights")
    rr_type = ET.SubElement(rec_rights, "lido:rightsType")
    ET.SubElement(rr_type, "lido:conceptID", {
        "lido:type": "http://terminology.lido-schema.org/lido00099",
        "lido:source": "CC",
    }).text = metadata_rights
    rr_holder = ET.SubElement(rec_rights, "lido:rightsHolder")
    rrh_name = ET.SubElement(rr_holder, "lido:legalBodyName")
    ET.SubElement(rrh_name, "lido:appellationValue").text = repo_name

    # Record Info Set (canonical portal URL)
    rec_info_set = ET.SubElement(rec_wrap, "lido:recordInfoSet")
    if ctx.record.canonical_url:
        ET.SubElement(rec_info_set, "lido:recordInfoLink").text = ctx.record.canonical_url
    rec_meta_date = ET.SubElement(rec_info_set, "lido:recordMetadataDate", {"lido:type": "created"})
    if ctx.record.created_at:
        rec_meta_date.text = ctx.record.created_at[:10]

    # 4c. resourceWrap (Public Media Representations)
    if ctx.media:
        res_wrap = ET.SubElement(admin_meta, "lido:resourceWrap")
        for m in ctx.media:
            if not m.is_public:
                continue
            rset = ET.SubElement(res_wrap, "lido:resourceSet")
            ET.SubElement(rset, "lido:resourceID", {
                "lido:type": "http://terminology.lido-schema.org/lido00100",
            }).text = idno

            rrep = ET.SubElement(rset, "lido:resourceRepresentation", {
                "lido:type": "http://terminology.lido-schema.org/lido00464",
            })
            ET.SubElement(rrep, "lido:linkResource", {
                "lido:formatResource": m.mime_type or "image/jpeg",
            }).text = m.url

            rtype_el = ET.SubElement(rset, "lido:resourceType")
            ET.SubElement(rtype_el, "lido:term").text = "Digitales Bild"

            # Resource rights
            rrights = ET.SubElement(rset, "lido:rightsResource")
            rr_type_el = ET.SubElement(rrights, "lido:rightsType")
            ET.SubElement(rr_type_el, "lido:conceptID", {
                "lido:type": "http://terminology.lido-schema.org/lido00099",
                "lido:source": "URI",
            }).text = m.license_uri or "http://rightsstatements.org/vocab/InC/1.0/"

            rr_holder_el = ET.SubElement(rrights, "lido:rightsHolder")
            rrh_name_el = ET.SubElement(rr_holder_el, "lido:legalBodyName")
            ET.SubElement(rrh_name_el, "lido:appellationValue").text = m.rights_holder or repo_name

    # Check for any generic target paths that were not handled above
    handled_prefixes = {
        "lido:objectClassificationWrap",
        "lido:objectIdentificationWrap",
        "lido:eventWrap",
        "lido:objectRelationWrap",
        "lido:rightsWorkWrap",
        "lido:recordWrap",
        "lido:resourceWrap",
    }
    for rule in mapping_set.rules:
        if not rule.is_enabled:
            continue
        if any(rule.target_key.startswith(p) for p in handled_prefixes):
            continue
        # Generic leaf insertion
        if rule.field_name:
            for val in extract_values(ctx, rule.field_name):
                append_path(lido_el, rule.target_key, _clean_text(val))

    return wrap
