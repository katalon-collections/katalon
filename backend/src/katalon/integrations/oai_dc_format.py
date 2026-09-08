# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportProfileCapabilities,
    ExportTargetCapability,
    LocalizedText,
    MetadataFormat,
    SourceKind,
    ValidatorDependency,
)
from katalon.services.metadata_mapping_service import extract_values

DC_NS = "http://purl.org/dc/elements/1.1/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

OAI_DC_TARGETS = {
    "dc:title",
    "dc:creator",
    "dc:subject",
    "dc:description",
    "dc:publisher",
    "dc:contributor",
    "dc:date",
    "dc:type",
    "dc:format",
    "dc:identifier",
    "dc:source",
    "dc:language",
    "dc:relation",
    "dc:coverage",
    "dc:rights",
}


class OaiDcFormat(MetadataFormat):
    key = "oai_dc"
    label = "OAI Dublin Core"
    targets = OAI_DC_TARGETS
    schema_url = "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
    namespace = "http://www.openarchives.org/OAI/2.0/oai_dc/"

    def capabilities(self) -> ExportProfileCapabilities:
        targets_def = [
            ("dc:title", "identification", "Titel", "Title", "Name oder Titel des Objekts", "Name or title of the resource", True),
            ("dc:creator", "agents", "Urheber / Schöpfer", "Creator", "Hauptverantwortliche Person oder Körperschaft", "Primary entity responsible for making the resource", False),
            ("dc:subject", "classification", "Thema / Schlagwort", "Subject", "Schlagwörter, Sachgruppen oder Themen", "Topic, keywords or classification", False),
            ("dc:description", "description", "Beschreibung", "Description", "Freitextbeschreibung oder Annotation", "Free text account of the resource", False),
            ("dc:publisher", "agents", "Verlag / Herausgeber", "Publisher", "Verantwortlich für Veröffentlichung oder Distribution", "Entity responsible for making the resource available", False),
            ("dc:contributor", "agents", "Beteiligte Person", "Contributor", "Mitwirkende Personen oder Institutionen", "Entity responsible for making contributions", False),
            ("dc:date", "dates", "Datum", "Date", "Entstehungs-, Publikations- oder Ereignisdatum", "Point or period of time associated with an event in lifecycle", False),
            ("dc:type", "identification", "Objekttyp", "Type", "Art oder Genre des Objekts (Standard: record_type)", "Nature or genre of the resource", False),
            ("dc:format", "technical", "Format / Medientyp", "Format", "Dateiformat oder physisches Medium", "File format, physical medium, or dimensions", False),
            ("dc:identifier", "identification", "Identifikator", "Identifier", "Signatur, Inventarnummer oder persistente ID", "Unambiguous reference to the resource within a given context", False),
            ("dc:source", "provenance", "Quelle", "Source", "Verweis auf Ausgangs- oder Vorlagendokument", "Related resource from which the described resource is derived", False),
            ("dc:language", "language", "Sprache", "Language", "Sprache des Inhalts (z. B. de, en, fre)", "Language of the resource", False),
            ("dc:relation", "relations", "Beziehung", "Relation", "Verweis auf verwandte Ressourcen", "Related resource", False),
            ("dc:coverage", "coverage", "Abdeckung (Ort/Zeit)", "Coverage", "Räumliche oder zeitliche Abdeckung", "Spatial or temporal topic of the resource", False),
            ("dc:rights", "rights", "Rechte / Lizenz", "Rights", "Rechteinhaber, Lizenz-URI oder Nutzungshinweis", "Information about rights held in and over the resource", False),
        ]
        caps = [
            ExportTargetCapability(
                key=key,
                group=group,
                label=LocalizedText(de=lde, en=len_),
                help=LocalizedText(de=hde, en=hen),
                source_kinds={SourceKind.FIELD, SourceKind.RELATION} if group in {"agents", "relations"} else {SourceKind.FIELD, SourceKind.RECORD, SourceKind.CONSTANT},
                required=req,
            )
            for key, group, lde, len_, hde, hen, req in targets_def
        ]
        return ExportProfileCapabilities(
            format_key=self.key,
            profile_id="oai_dc_simple",
            profile_version="2.0",
            label=LocalizedText(de="OAI Dublin Core (Einfach)", en="OAI Dublin Core (Simple)"),
            targets=caps,
            validators=[ValidatorDependency(name="OAI-PMH Dublin Core Schema", version="2.0", available=True)],
        )
    def render(
        self, hit: dict[str, Any], mappings: CompiledMappingSet | dict[str, list[str]]
    ) -> ET.Element:
        src = hit["_source"]
        record_id = hit["_id"]
        record_type = src.get("record_type", "")
        md: dict[str, Any] = src.get("metadata", {})

        dc = ET.Element("oai_dc:dc", {
            "xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
            "xmlns:dc": DC_NS,
            "xmlns:xsi": XSI_NS,
            "xsi:schemaLocation": (
                "http://www.openarchives.org/OAI/2.0/oai_dc/ "
                "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
            ),
        })

        mapping_set = (
            mappings
            if isinstance(mappings, CompiledMappingSet)
            else CompiledMappingSet.from_legacy_dict(self.key, record_type, mappings)
        )

        mapped_targets: set[str] = set()
        for rule in mapping_set.rules:
            if not rule.is_enabled:
                continue
            field_name = rule.field_name
            if not field_name:
                continue
            for value in extract_values(src, field_name):
                if prefix := rule.settings.get("prefix"):
                    value = f"{prefix}{value}"
                mapped_targets.add(rule.target_key)
                if rule.target_key.startswith("dc:"):
                    ET.SubElement(dc, rule.target_key).text = value
        if "dc:type" not in mapped_targets:
            ET.SubElement(dc, "dc:type").text = record_type

        ET.SubElement(dc, "dc:identifier").text = f"oai:katalon:{record_type}:{record_id}"
        if idno := src.get("idno") or md.get("idno"):
            ET.SubElement(dc, "dc:identifier").text = str(idno)

        return dc
