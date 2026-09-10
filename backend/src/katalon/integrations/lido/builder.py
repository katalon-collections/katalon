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
        for relation in ctx.relations:
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
    work_type_values = values("lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType")
    for value in work_type_values or [""]:
        work_type = ET.SubElement(work_type_wrap, "lido:objectWorkType")
        ET.SubElement(work_type, "lido:term").text = value

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

    actor_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue"
    event_type_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventType/lido:term"
    date_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate"
    earliest_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate"
    event_types = values(event_type_target)
    actors, dates, earliest_dates = values(actor_target), values(date_target), values(earliest_target)
    if event_types or actors or dates or earliest_dates:
        event_wrap = ET.SubElement(descriptive, "lido:eventWrap")
        event = ET.SubElement(ET.SubElement(event_wrap, "lido:eventSet"), "lido:event")
        event_type = ET.SubElement(event, "lido:eventType")
        for value in event_types or [""]:
            ET.SubElement(event_type, "lido:term").text = value
        for rule in rules_by_target.get(actor_target, []):
            role = _clean_text(rule.settings.get("role") or rule.source_config.get("role"))
            for value in _rule_values(ctx, rule):
                actor_in_role = ET.SubElement(ET.SubElement(event, "lido:eventActor"), "lido:actorInRole")
                actor = ET.SubElement(actor_in_role, "lido:actor")
                actor_name = ET.SubElement(actor, "lido:nameActorSet")
                ET.SubElement(actor_name, "lido:appellationValue").text = value
                if role:
                    role_actor = ET.SubElement(actor_in_role, "lido:roleActor")
                    ET.SubElement(role_actor, "lido:term").text = role
        if dates or earliest_dates:
            event_date = ET.SubElement(event, "lido:eventDate")
            for value in dates:
                ET.SubElement(event_date, "lido:displayDate").text = value
            if earliest_dates:
                date = ET.SubElement(event_date, "lido:date")
                for value in earliest_dates:
                    ET.SubElement(date, "lido:earliestDate").text = value

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
        "lido:type": "http://terminology.lido-schema.org/lido00099",
    }).text = idno
    record_type = ET.SubElement(record_wrap, "lido:recordType")
    ET.SubElement(record_type, "lido:term").text = "Einzelobjekt"
    record_source = ET.SubElement(record_wrap, "lido:recordSource")
    if institution_name:
        legal_name = ET.SubElement(record_source, "lido:legalBodyName")
        ET.SubElement(legal_name, "lido:appellationValue").text = institution_name
        if website:
            ET.SubElement(record_source, "lido:legalBodyWeblink").text = website
    resource_values = values("lido:administrativeMetadata/lido:resourceWrap/lido:resourceSet/lido:resourceRepresentation/lido:linkResource")
    if resource_values:
        resource_wrap = ET.SubElement(administrative, "lido:resourceWrap")
        for value in resource_values:
            resource_set = ET.SubElement(resource_wrap, "lido:resourceSet")
            representation = ET.SubElement(resource_set, "lido:resourceRepresentation")
            ET.SubElement(representation, "lido:linkResource").text = value

    return wrap
