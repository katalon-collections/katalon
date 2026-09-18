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
)
from katalon.services.metadata_mapping_service import extract_values

LIDO_NS = "http://www.lido-schema.org"
GML_NS = "http://www.opengis.net/gml"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = "http://www.lido-schema.org http://www.lido-schema.org/schema/v1.0/lido-v1.0.xsd"


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
        relation_type = rule.source_config.get("relation_type")
        target_field = rule.source_config.get("target_field")
        direction = str(rule.source_config.get("direction") or "outbound")
        for relation in ctx.relations:
            if relation.direction != direction:
                continue
            if relation_type and relation.relation_type != relation_type:
                continue
            values.append(
                relation.target_values.get(target_field)
                if target_field
                else (relation.target_label or relation.target_idno)
            )
    elif rule.source_kind == SourceKind.RECORD:
        property_name = rule.source_config.get("property")
        if property_name and (value := getattr(ctx.record, property_name, None)):
            values = [value]
    elif rule.source_kind == SourceKind.CONSTANT:
        values = [rule.source_config.get("value") or rule.settings.get("value")]
    elif rule.source_kind == SourceKind.MEDIA:
        property_name = rule.source_config.get("property", "url")
        values = [getattr(media, property_name, None) for media in ctx.media if media.is_public]

    prefix = rule.settings.get("prefix", "")
    return [f"{prefix}{value}" for value in (_clean_text(value) for value in values) if value]


def _get_work_type_concepts(ctx: ExportRecordContext, mapping_set: CompiledMappingSet) -> list[dict[str, Any]]:
    target = "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"
    rules = [r for r in mapping_set.rules if r.target_key == target and r.is_enabled]
    results: list[dict[str, Any]] = []

    for rule in rules:
        if rule.source_kind == SourceKind.FIELD and rule.field_name:
            raw_val = ctx.fields.get(rule.field_name)
            items = raw_val if isinstance(raw_val, list) else ([raw_val] if raw_val is not None else [])
            for item in items:
                if isinstance(item, dict):
                    cid = item.get("external_id") or item.get("id") or item.get("concept_id")
                    curi = item.get("uri") or item.get("concept_uri")
                    csrc = item.get("source") or item.get("authority_source")
                    term = item.get("label") or item.get("term") or item.get("value")
                    if cid or curi or term:
                        results.append({
                            "id": cid,
                            "uri": curi,
                            "source": csrc,
                            "term": str(term or ""),
                        })
                elif item != "":
                    term_str = str(item)
                    results.append({
                        "id": ctx.record.subtype_concept_id,
                        "uri": ctx.record.subtype_concept_uri,
                        "source": ctx.record.subtype_concept_source,
                        "term": term_str,
                    })
        elif rule.source_kind == SourceKind.RECORD and (
            ctx.record.subtype_concept_id or ctx.record.subtype_concept_uri
        ):
            results.append({
                "id": ctx.record.subtype_concept_id,
                "uri": ctx.record.subtype_concept_uri,
                "source": ctx.record.subtype_concept_source,
                "term": (
                    ctx.record.subtype_concept_label
                    or str(getattr(ctx.record, rule.source_config.get("property", "target_subtype"), None) or ctx.record.target_subtype or "")
                ),
            })
        elif rule.source_kind == SourceKind.CONSTANT:
            const_val = rule.source_config.get("value") or rule.settings.get("value")
            if const_val:
                results.append({
                    "id": None,
                    "uri": None,
                    "source": None,
                    "term": str(const_val),
                })

    if not results and not any(rule.source_kind == SourceKind.RECORD for rule in rules):
        # Fallback to rule-extracted values or record subtype
        extracted = []
        for rule in rules:
            extracted.extend(_rule_values(ctx, rule))
        if extracted:
            for val in extracted:
                results.append({
                    "id": ctx.record.subtype_concept_id,
                    "uri": ctx.record.subtype_concept_uri,
                    "source": ctx.record.subtype_concept_source,
                    "term": val,
                })
        else:
            results.append({
                "id": ctx.record.subtype_concept_id,
                "uri": ctx.record.subtype_concept_uri,
                "source": ctx.record.subtype_concept_source,
                "term": ctx.record.subtype_concept_label or ctx.record.target_subtype or "",
            })

    return results


def build_lido_element(
    ctx: ExportRecordContext,
    mapping_set: CompiledMappingSet,
    institution_config: dict[str, Any] | None = None,
) -> ET.Element:
    """Build a LIDO 1.0 envelope from explicit mappings and institution values."""
    config = institution_config or {}
    rules_by_target = mapping_set.by_target()

    def values(target_key: str) -> list[str]:
        return [value for rule in rules_by_target.get(target_key, []) for value in _rule_values(ctx, rule)]

    def config_value(key: str, legacy_key: str | None = None) -> str:
        return _clean_text(config.get(key) or (config.get(legacy_key) if legacy_key else None))

    idno = ctx.record.idno or ctx.record.id
    isil = config_value("isil")
    institution_name = config_value("institution_name", "repository_name")
    website = config_value("website", "repository_url")
    location = config_value("location", "repository_location")

    portal_host = config_value("portal_host").rstrip("/")
    portal_paths = {
        "object": "objects",
        "entity": "entities",
        "place": "places",
        "occurrence": "occurrences",
        "collection": "collections",
    }
    record_info_link = (
        f"{portal_host}/{portal_paths[ctx.record.record_type]}/{ctx.record.id}"
        if portal_host and ctx.record.record_type in portal_paths
        else ctx.record.canonical_url
    )
    record_rights = config_value("record_rights") or "https://creativecommons.org/publicdomain/zero/1.0/"

    wrap = ET.Element("lido:lidoWrap", {
        "xmlns:lido": LIDO_NS,
        "xmlns:gml": GML_NS,
        "xmlns:xsi": XSI_NS,
        "xsi:schemaLocation": SCHEMA_LOC,
    })
    lido = ET.SubElement(wrap, "lido:lido")
    ET.SubElement(lido, "lido:lidoRecID", {"lido:type": "http://terminology.lido-schema.org/lido00100"}).text = (
        f"{isil}--{idno}" if isil else idno
    )

    category = ET.SubElement(lido, "lido:category")
    ET.SubElement(category, "lido:conceptID", {
        "lido:type": "http://terminology.lido-schema.org/lido00099",
        "lido:source": "CIDOC CRM",
    }).text = "http://www.cidoc-crm.org/cidoc-crm/E22_Human-Made_Object"

    descriptive = ET.SubElement(lido, "lido:descriptiveMetadata", {"xml:lang": "de"})
    classification = ET.SubElement(descriptive, "lido:objectClassificationWrap")
    work_type_wrap = ET.SubElement(classification, "lido:objectWorkTypeWrap")
    work_types = _get_work_type_concepts(ctx, mapping_set)
    for wt in work_types:
        work_type = ET.SubElement(work_type_wrap, "lido:objectWorkType")
        concept_val = wt.get("uri") or wt.get("id")
        if concept_val:
            cid_attrs = {"lido:type": "URI"}
            if wt.get("source"):
                cid_attrs["lido:source"] = wt["source"].upper() if wt["source"] in {"aat", "gnd"} else wt["source"]
            ET.SubElement(work_type, "lido:conceptID", cid_attrs).text = str(concept_val)
        ET.SubElement(work_type, "lido:term").text = wt.get("term") or ""

    collection_values = values("lido:objectClassificationWrap/lido:classificationWrap/lido:classification")
    if collection_values:
        collection_wrap = ET.SubElement(classification, "lido:classificationWrap")
        for value in collection_values:
            item = ET.SubElement(collection_wrap, "lido:classification")
            ET.SubElement(item, "lido:term").text = value

    identification = ET.SubElement(descriptive, "lido:objectIdentificationWrap")
    title_wrap = ET.SubElement(identification, "lido:titleWrap")
    title_values = values("lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue")
    for value in title_values or [""]:
        title_set = ET.SubElement(title_wrap, "lido:titleSet")
        ET.SubElement(title_set, "lido:appellationValue", {"lido:pref": "preferred"}).text = value

    optional_sections = (
        ("lido:objectIdentificationWrap/lido:inscriptionsWrap/lido:inscriptions/lido:inscriptionTranscription", "lido:inscriptionsWrap", "lido:inscriptions", "lido:inscriptionTranscription"),
        ("lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue", "lido:objectDescriptionWrap", "lido:objectDescriptionSet", "lido:descriptiveNoteValue"),
        ("lido:objectIdentificationWrap/lido:objectMeasurementsWrap/lido:objectMeasurementsSet/lido:displayObjectMeasurements", "lido:objectMeasurementsWrap", "lido:objectMeasurementsSet", "lido:displayObjectMeasurements"),
    )
    for target, wrap_tag, set_tag, value_tag in optional_sections:
        if section_values := values(target):
            section_wrap = ET.SubElement(identification, wrap_tag)
            for value in section_values:
                section_set = ET.SubElement(section_wrap, set_tag)
                ET.SubElement(section_set, value_tag).text = value

    if institution_name:
        repository_wrap = ET.SubElement(identification, "lido:repositoryWrap")
        repository_set = ET.SubElement(repository_wrap, "lido:repositorySet", {"lido:type": "current"})
        repository_name = ET.SubElement(repository_set, "lido:repositoryName")
        if isil:
            ET.SubElement(repository_name, "lido:legalBodyID", {
                "lido:type": "http://terminology.lido-schema.org/lido00100",
                "lido:source": "ISIL",
            }).text = f"https://sigel.staatsbibliothek-berlin.de/suche?isil={isil}"
        legal_name = ET.SubElement(repository_name, "lido:legalBodyName")
        ET.SubElement(legal_name, "lido:appellationValue").text = institution_name
        if website:
            ET.SubElement(repository_name, "lido:legalBodyWeblink").text = website
        if location:
            repository_location = ET.SubElement(repository_set, "lido:repositoryLocation")
            name_place_set = ET.SubElement(repository_location, "lido:namePlaceSet")
            ET.SubElement(name_place_set, "lido:appellationValue").text = location
        ET.SubElement(repository_set, "lido:workID", {"lido:type": "Objekt-Signatur"}).text = idno

    configured_events = config.get("lido_events")
    event_specs: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()

    if isinstance(configured_events, list):
        for ev in configured_events:
            eid = str(ev.get("id") or "").strip()
            if eid and eid not in seen_event_ids:
                seen_event_ids.add(eid)
                event_specs.append(ev)

    if "production" not in seen_event_ids:
        seen_event_ids.add("production")
        event_specs.insert(0, {
            "id": "production",
            "type": "Herstellung",
            "label_de": "Herstellung / Entstehung",
            "label_en": "Production / Creation",
        })

    for target_key in rules_by_target.keys():
        if target_key.startswith("lido:events/"):
            parts = target_key.split("/")
            if len(parts) >= 2:
                eid = parts[1]
                if eid not in seen_event_ids:
                    seen_event_ids.add(eid)
                    event_specs.append({"id": eid, "type": eid.capitalize()})

    legacy_actor_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue"
    legacy_event_type_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventType/lido:term"
    legacy_date_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate"
    legacy_earliest_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate"
    legacy_place_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventPlace/lido:displayPlace"

    event_sets_to_render = []
    for ev in event_specs:
        eid = ev.get("id")
        preset_type = ev.get("type") or "Herstellung"

        type_rules = list(rules_by_target.get(f"lido:events/{eid}/type", []))
        actor_rules = list(rules_by_target.get(f"lido:events/{eid}/actor", []))
        date_rules = list(rules_by_target.get(f"lido:events/{eid}/date", []))
        earliest_rules = list(rules_by_target.get(f"lido:events/{eid}/earliest_date", []))
        place_rules = list(rules_by_target.get(f"lido:events/{eid}/place", []))

        if eid == "production":
            type_rules.extend(rules_by_target.get(legacy_event_type_target, []))
            actor_rules.extend(rules_by_target.get(legacy_actor_target, []))
            date_rules.extend(rules_by_target.get(legacy_date_target, []))
            earliest_rules.extend(rules_by_target.get(legacy_earliest_target, []))
            place_rules.extend(rules_by_target.get(legacy_place_target, []))

        ev_types = [val for r in type_rules for val in _rule_values(ctx, r)]
        ev_actors: list[tuple[MappingSpec, str]] = [(r, val) for r in actor_rules for val in _rule_values(ctx, r)]
        ev_dates = [val for r in date_rules for val in _rule_values(ctx, r)]
        ev_earliest = [val for r in earliest_rules for val in _rule_values(ctx, r)]
        ev_places = [val for r in place_rules for val in _rule_values(ctx, r)]

        if ev_types or ev_actors or ev_dates or ev_earliest or ev_places:
            event_type_name = ev_types[0] if ev_types else preset_type
            event_sets_to_render.append({
                "type": event_type_name,
                "actors": ev_actors,
                "dates": ev_dates,
                "earliest_dates": ev_earliest,
                "places": ev_places,
            })

    if event_sets_to_render:
        event_wrap = ET.SubElement(descriptive, "lido:eventWrap")
        for ev_data in event_sets_to_render:
            event = ET.SubElement(ET.SubElement(event_wrap, "lido:eventSet"), "lido:event")
            event_type = ET.SubElement(event, "lido:eventType")
            if ev_data["type"].casefold() == "herstellung":
                ET.SubElement(event_type, "lido:conceptID", {
                    "lido:type": "http://terminology.lido-schema.org/lido00099",
                }).text = "http://terminology.lido-schema.org/lido00007"
            ET.SubElement(event_type, "lido:term").text = ev_data["type"]

            for rule, actor_val in ev_data["actors"]:
                actor_in_role = ET.SubElement(ET.SubElement(event, "lido:eventActor"), "lido:actorInRole")
                actor = ET.SubElement(actor_in_role, "lido:actor")
                actor_name = ET.SubElement(actor, "lido:nameActorSet")
                ET.SubElement(actor_name, "lido:appellationValue").text = actor_val
                role = _clean_text(rule.settings.get("role") or rule.source_config.get("role"))
                if role:
                    role_actor = ET.SubElement(actor_in_role, "lido:roleActor")
                    ET.SubElement(role_actor, "lido:term").text = role

            if ev_data["dates"] or ev_data["earliest_dates"]:
                event_date = ET.SubElement(event, "lido:eventDate")
                for d_val in ev_data["dates"]:
                    ET.SubElement(event_date, "lido:displayDate").text = d_val
                if ev_data["earliest_dates"]:
                    date_elem = ET.SubElement(event_date, "lido:date")
                    for ed_val in ev_data["earliest_dates"]:
                        ET.SubElement(date_elem, "lido:earliestDate").text = ed_val

            for p_val in ev_data["places"]:
                event_place = ET.SubElement(event, "lido:eventPlace")
                ET.SubElement(event_place, "lido:displayPlace").text = p_val

    subject_values = values("lido:objectRelationWrap/lido:subjectWrap/lido:subjectSet/lido:subject/lido:subjectConcept/lido:term")
    if subject_values:
        relation_wrap = ET.SubElement(descriptive, "lido:objectRelationWrap")
        subject_wrap = ET.SubElement(relation_wrap, "lido:subjectWrap")
        for value in subject_values:
            subject = ET.SubElement(ET.SubElement(subject_wrap, "lido:subjectSet"), "lido:subject")
            concept = ET.SubElement(subject, "lido:subjectConcept")
            ET.SubElement(concept, "lido:term").text = value

    administrative = ET.SubElement(lido, "lido:administrativeMetadata", {"xml:lang": "de"})
    rights_values = values("lido:rightsWorkWrap/lido:rightsWorkSet/lido:rightsType/lido:term")
    if rights_values:
        rights_set = ET.SubElement(ET.SubElement(administrative, "lido:rightsWorkWrap"), "lido:rightsWorkSet")
        for value in rights_values:
            rights_type = ET.SubElement(rights_set, "lido:rightsType")
            ET.SubElement(rights_type, "lido:term").text = value

    record_wrap = ET.SubElement(administrative, "lido:recordWrap")
    ET.SubElement(record_wrap, "lido:recordID", {
        "lido:type": "http://terminology.lido-schema.org/lido00100",
    }).text = idno
    record_type = ET.SubElement(record_wrap, "lido:recordType")
    ET.SubElement(record_type, "lido:conceptID", {
        "lido:type": "http://terminology.lido-schema.org/lido00099",
    }).text = "http://terminology.lido-schema.org/lido00141"
    ET.SubElement(record_type, "lido:term").text = "Einzelobjekt"
    record_source = ET.SubElement(record_wrap, "lido:recordSource")
    if isil:
        ET.SubElement(record_source, "lido:legalBodyID", {
            "lido:type": "http://terminology.lido-schema.org/lido00099",
        }).text = f"https://ld.zdb-services.de/resource/organisations/{isil}"
    if institution_name:
        legal_name = ET.SubElement(record_source, "lido:legalBodyName")
        ET.SubElement(legal_name, "lido:appellationValue").text = institution_name
    if website:
        ET.SubElement(record_source, "lido:legalBodyWeblink").text = website

    record_rights_elem = ET.SubElement(record_wrap, "lido:recordRights")
    rights_type = ET.SubElement(record_rights_elem, "lido:rightsType")
    ET.SubElement(rights_type, "lido:conceptID", {"lido:type": "URI"}).text = record_rights

    record_info = ET.SubElement(record_wrap, "lido:recordInfoSet")
    if record_info_link:
        ET.SubElement(record_info, "lido:recordInfoLink").text = record_info_link
    ET.SubElement(record_info, "lido:recordMetadataDate").text = datetime.now(UTC).isoformat()
    resource_values = values("lido:administrativeMetadata/lido:resourceWrap/lido:resourceSet/lido:resourceRepresentation/lido:linkResource")
    if resource_values:
        resource_wrap = ET.SubElement(administrative, "lido:resourceWrap")
        for value in resource_values:
            resource_set = ET.SubElement(resource_wrap, "lido:resourceSet")
            representation = ET.SubElement(resource_set, "lido:resourceRepresentation")
            ET.SubElement(representation, "lido:linkResource").text = value

    return wrap
