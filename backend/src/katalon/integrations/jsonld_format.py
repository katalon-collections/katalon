# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.metadata_format import MetadataFormat
from katalon.services.metadata_mapping_service import extract_values

CRM_NS = "http://www.cidoc-crm.org/cidoc-crm/"
LRMOO_NS = "http://iflastandards.info/ns/lrm/lrmoo/"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"
DCTERMS_NS = "http://purl.org/dc/terms/"
JSONLD_NS = "http://www.w3.org/ns/json-ld"

JSONLD_CONTEXT: dict[str, Any] = {
    "crm": CRM_NS,
    "lrmoo": LRMOO_NS,
    "skos": SKOS_NS,
    "rdfs": RDFS_NS,
    "xsd": XSD_NS,
    "dcterms": DCTERMS_NS,
}

JSONLD_TARGETS: set[str] = {
    "crm:P1_is_identified_by",
    "crm:P2_has_type",
    "crm:P3_has_note",
    "crm:P4_has_time-span",
    "crm:P7_took_place_at",
    "crm:P14_carried_out_by",
    "crm:P46_is_composed_of",
    "crm:P52_has_current_owner",
    "crm:P53_has_former_or_current_location",
    "crm:P62_depicts",
    "crm:P67_refers_to",
    "crm:P102_has_title",
    "crm:P108_has_produced",
    "crm:P128_carries",
    "crm:P138_represents",
    "crm:P168_place_is_defined_by",
    "lrmoo:R3_is_realised_in",
    "lrmoo:R4_is_embodied_in",
    "lrmoo:R7_exemplifies",
    "rdfs:label",
    "skos:Concept",
}

RELATION_PROPERTY_MAP: dict[str, str] = {
    # LRMoo
    "is_realised_in": "lrmoo:R3_is_realised_in",
    "realised_in": "lrmoo:R3_is_realised_in",
    "r3_is_realised_in": "lrmoo:R3_is_realised_in",
    "realisiert_in": "lrmoo:R3_is_realised_in",
    "realisiert": "lrmoo:R3_is_realised_in",

    "is_embodied_in": "lrmoo:R4_is_embodied_in",
    "embodied_in": "lrmoo:R4_is_embodied_in",
    "r4_is_embodied_in": "lrmoo:R4_is_embodied_in",
    "verkoerpert_in": "lrmoo:R4_is_embodied_in",
    "verkoerpert": "lrmoo:R4_is_embodied_in",

    "exemplifies": "lrmoo:R7_exemplifies",
    "r7_exemplifies": "lrmoo:R7_exemplifies",
    "exemplar_von": "lrmoo:R7_exemplifies",
    "exemplifiziert": "lrmoo:R7_exemplifies",

    # CIDOC-CRM
    "carried_out_by": "crm:P14_carried_out_by",
    "p14_carried_out_by": "crm:P14_carried_out_by",
    "ausgefuehrt_von": "crm:P14_carried_out_by",
    "verfasst_von": "crm:P14_carried_out_by",
    "komponiert_von": "crm:P14_carried_out_by",
    "fotografiert_von": "crm:P14_carried_out_by",
    "hergestellt_von": "crm:P14_carried_out_by",
    "creator": "crm:P14_carried_out_by",
    "author": "crm:P14_carried_out_by",
    "urheber": "crm:P14_carried_out_by",

    "depicts": "crm:P138_represents",
    "shows": "crm:P138_represents",
    "zeigt": "crm:P138_represents",
    "illustriert": "crm:P138_represents",
    "abgebildete_person": "crm:P138_represents",
    "represents": "crm:P138_represents",
    "p138_represents": "crm:P138_represents",

    "took_place_at": "crm:P7_took_place_at",
    "p7_took_place_at": "crm:P7_took_place_at",
    "spielt_in": "crm:P7_took_place_at",
    "aufgenommen_in": "crm:P7_took_place_at",
    "ort": "crm:P7_took_place_at",
    "fundort": "crm:P7_took_place_at",
    "geboren_in": "crm:P7_took_place_at",
    "gestorben_in": "crm:P7_took_place_at",

    "refers_to": "crm:P67_refers_to",
    "p67_refers_to": "crm:P67_refers_to",
    "bezieht_sich_auf": "crm:P67_refers_to",
    "related_to": "crm:P67_refers_to",

    "contains": "crm:P46_is_composed_of",
    "p46_is_composed_of": "crm:P46_is_composed_of",
    "enthaelt": "crm:P46_is_composed_of",
    "part_of": "crm:P46_is_composed_of",
    "teil_von": "crm:P46_is_composed_of",

    "has_current_owner": "crm:P52_has_current_owner",
    "eigentuemer": "crm:P52_has_current_owner",
    "vorbesitzer": "crm:P51_has_former_or_current_owner",
}

INVERSE_PROPERTY_MAP: dict[str, str] = {
    "lrmoo:R3_is_realised_in": "lrmoo:R3i_realises",
    "lrmoo:R4_is_embodied_in": "lrmoo:R4i_embodies",
    "lrmoo:R7_exemplifies": "lrmoo:R7i_is_exemplified_by",
    "crm:P14_carried_out_by": "crm:P14i_performed",
    "crm:P138_represents": "crm:P138i_is_represented_by",
    "crm:P7_took_place_at": "crm:P7i_witnessed",
    "crm:P67_refers_to": "crm:P67i_is_referred_to_by",
    "crm:P46_is_composed_of": "crm:P46i_forms_part_of",
    "crm:P52_has_current_owner": "crm:P52i_is_current_owner_of",
    "crm:P51_has_former_or_current_owner": "crm:P51i_is_former_or_current_owner_of",
}


PLURAL_TYPE_MAP: dict[str, str] = {
    "entity": "entities",
    "occurrence": "occurrences",
    "object": "objects",
    "place": "places",
    "procedure": "procedures",
}


def record_uri_path(record_type: str, record_id: str, base_url: str = "") -> str:
    clean_base = base_url.rstrip("/") if base_url else ""
    plural = PLURAL_TYPE_MAP.get(record_type, f"{record_type}s")
    if clean_base:
        return f"{clean_base}/api/v1/{plural}/{record_id}"
    return f"urn:katalon:{record_type}:{record_id}"

def map_primary_type(record_type: str, subtype: str | None = None) -> list[str] | str:
    """Map Katalon primary record type and optional subtype to CIDOC-CRM / LRMoo classes."""
    norm_subtype = (subtype or "").lower().strip()

    if record_type == "occurrence":
        if norm_subtype in ("work", "werk"):
            return "lrmoo:F1_Work"
        elif norm_subtype in ("expression", "ausgabe", "fassung"):
            return "lrmoo:F2_Expression"
        elif norm_subtype in ("manifestation", "ausgabeform"):
            return "lrmoo:F3_Manifestation"
        elif norm_subtype in ("event", "ereignis", "ausstellung", "performance"):
            return "crm:E5_Event"
        else:
            if "work" in norm_subtype or "werk" in norm_subtype:
                return "lrmoo:F1_Work"
            if "expr" in norm_subtype:
                return "lrmoo:F2_Expression"
            if "manif" in norm_subtype:
                return "lrmoo:F3_Manifestation"
            return "crm:E5_Event"

    elif record_type == "object":
        return ["crm:E22_Human-Made_Object", "lrmoo:F5_Item"]

    elif record_type == "entity":
        if norm_subtype in (
            "group",
            "organization",
            "organisation",
            "institution",
            "corporation",
            "koerperschaft",
        ):
            return "crm:E74_Group"
        elif norm_subtype in ("person", "individual", "human"):
            return "crm:E21_Person"
        else:
            return "crm:E21_Person"

    elif record_type == "place":
        return "crm:E53_Place"

    elif record_type == "procedure":
        return "crm:E7_Activity"

    return "crm:E1_CRM_Entity"


def map_relation_property(relation_type: str, is_inverse: bool = False) -> str:
    """Map a relation type to standard CIDOC-CRM or LRMoo property."""
    rel_clean = (relation_type or "").strip()
    if not rel_clean:
        prop = "crm:P67_refers_to"
    elif ":" in rel_clean or rel_clean.startswith("http://") or rel_clean.startswith("https://"):
        prop = rel_clean
    else:
        prop = RELATION_PROPERTY_MAP.get(rel_clean.lower(), "crm:P67_refers_to")

    if is_inverse:
        return INVERSE_PROPERTY_MAP.get(prop, f"{prop}_inverse")
    return prop


def build_jsonld_doc(
    record_type: str,
    record_id: str,
    title: str | None = None,
    idno: str | None = None,
    subtype: str | None = None,
    subtype_label: str | None = None,
    metadata: dict[str, Any] | None = None,
    relations: list[dict[str, Any]] | None = None,
    vocab_concepts: dict[str, dict[str, Any]] | None = None,
    mappings: dict[str, list[str]] | None = None,
    base_url: str = "",
    media_files: list[dict[str, Any]] | None = None,
    geo_point: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Construct a full JSON-LD document conforming to CIDOC-CRM & LRMoo."""
    md = dict(metadata or {})
    clean_base = base_url.rstrip("/") if base_url else ""
    type_class = map_primary_type(record_type, subtype)

    record_uri = record_uri_path(record_type, str(record_id), base_url)

    doc: dict[str, Any] = {
        "@context": JSONLD_CONTEXT,
        "@id": record_uri,
        "@type": type_class,
    }

    display_title = title or idno or record_id
    doc["rdfs:label"] = display_title
    if title:
        doc["crm:P102_has_title"] = title

    identified_by: list[dict[str, Any]] = []
    if title:
        identified_by.append({
            "@type": "crm:E35_Title",
            "rdfs:label": title,
        })
    if idno:
        identified_by.append({
            "@type": "crm:E42_Identifier",
            "crm:P190_has_symbolic_content": idno,
            "rdfs:label": idno,
        })
    if identified_by:
        doc["crm:P1_is_identified_by"] = identified_by if len(identified_by) > 1 else identified_by[0]

    # Description/Note
    note_candidates = [
        md.get("beschreibung"),
        md.get("description"),
        md.get("note"),
        md.get("biografie"),
    ]
    for note_val in note_candidates:
        if note_val and isinstance(note_val, str) and note_val.strip():
            doc["crm:P3_has_note"] = note_val.strip()
            break

    # Subtype as type classification
    types_list: list[Any] = []
    if subtype:
        types_list.append({
            "@type": "crm:E55_Type",
            "rdfs:label": subtype_label or subtype,
        })
    # Concept resolution for vocabulary terms
    concepts_map = vocab_concepts or {}
    for field_name, val in md.items():
        terms_to_check: list[str] = []
        if isinstance(val, str) and val in concepts_map:
            terms_to_check.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item in concepts_map:
                    terms_to_check.append(item)

        for term_code in terms_to_check:
            concept_obj = concepts_map[term_code]
            if concept_obj not in types_list:
                types_list.append(concept_obj)

    if types_list:
        doc["crm:P2_has_type"] = types_list if len(types_list) > 1 else types_list[0]

    # Geo coordinates for Places
    if geo_point:
        lon, lat = geo_point
        doc["crm:P168_place_is_defined_by"] = f"POINT({lon} {lat})"

    # Media files for Objects
    if media_files:
        representations: list[dict[str, Any]] = []
        for media in media_files:
            media_id = media.get("id")
            manifest_uri = media.get("manifest_uri")
            image_uri = media.get("image_uri")
            if manifest_uri:
                representations.append({
                    "@type": "crm:E73_Information_Object",
                    "@id": manifest_uri,
                    "dcterms:conformsTo": "http://iiif.io/api/presentation/3/context.json",
                    "rdfs:label": media.get("filename") or "IIIF Manifest",
                })
            elif image_uri:
                representations.append({
                    "@type": "crm:E36_Visual_Item",
                    "@id": image_uri,
                    "rdfs:label": media.get("filename") or "Media File",
                })
            elif media_id and clean_base:
                representations.append({
                    "@type": "crm:E36_Visual_Item",
                    "@id": f"{clean_base}/api/v1/media/{media_id}",
                    "rdfs:label": media.get("filename") or "Media File",
                })
        if representations:
            doc["crm:P138i_has_representation"] = (
                representations if len(representations) > 1 else representations[0]
            )

    # Relations (with target deduplication by @id per property)
    if relations:
        rel_by_prop: dict[str, list[dict[str, Any]]] = {}
        seen_by_prop: dict[str, set[str]] = {}
        for rel in relations:
            target_type = rel.get("target_type") or rel.get("to_type") or "object"
            target_id = rel.get("target_id") or rel.get("to_id") or ""
            target_label = rel.get("label") or rel.get("to_label") or rel.get("from_label")
            target_subtype = rel.get("target_subtype")
            rel_type = rel.get("relation_type", "")
            is_incoming = str(rel.get("to_id", "")) == str(record_id) and bool(record_id)

            prop = map_relation_property(rel_type, is_inverse=is_incoming)
            target_uri = record_uri_path(target_type, str(target_id), base_url)

            seen = seen_by_prop.setdefault(prop, set())
            if target_uri in seen:
                continue
            seen.add(target_uri)

            target_cls = map_primary_type(target_type, target_subtype)
            target_node: dict[str, Any] = {
                "@id": target_uri,
                "@type": target_cls,
            }
            if target_label:
                target_node["rdfs:label"] = str(target_label)

            rel_by_prop.setdefault(prop, []).append(target_node)

        for prop, nodes in rel_by_prop.items():
            doc[prop] = nodes if len(nodes) > 1 else nodes[0]

    # Explicit mappings from MetadataMapping
    if mappings:
        for field_name, target_paths in mappings.items():
            vals = extract_values({"metadata": md, "idno": idno}, field_name)
            for path in target_paths:
                if not vals:
                    continue
                # If path is already populated, don't overwrite with empty
                if path in doc:
                    existing = doc[path]
                    if not isinstance(existing, list):
                        existing = [existing]
                    doc[path] = existing + vals
                else:
                    doc[path] = vals if len(vals) > 1 else vals[0]

    return doc


class JsonLdFormat(MetadataFormat):
    key = "json_ld"
    label = "CIDOC-CRM & LRMoo (JSON-LD)"
    targets = JSONLD_TARGETS
    schema_url = "http://www.w3.org/ns/json-ld"
    namespace = JSONLD_NS

    def render(self, hit: dict[str, Any], mappings: dict[str, list[str]]) -> ET.Element:
        src = hit.get("_source", {})
        record_id = str(hit.get("_id", ""))
        record_type = src.get("record_type", "object")
        title = src.get("title")
        idno = src.get("idno")
        metadata = src.get("metadata", {})
        subtype = src.get("subtype") or metadata.get("subtype")

        relations: list[dict[str, Any]] = []
        for adv_rel in src.get("adv_relations", []):
            relations.append({
                "target_type": adv_rel.get("target_type"),
                "target_id": adv_rel.get("target_id"),
                "relation_type": adv_rel.get("relation_type"),
            })

        doc = build_jsonld_doc(
            record_type=record_type,
            record_id=record_id,
            title=title,
            idno=idno,
            subtype=subtype,
            metadata=metadata,
            relations=relations,
            mappings=mappings,
        )

        el = ET.Element("json_ld", {"xmlns": self.namespace})
        el.text = json.dumps(doc, indent=2, ensure_ascii=False)
        return el
