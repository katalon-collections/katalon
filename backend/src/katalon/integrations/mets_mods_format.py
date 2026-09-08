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
    append_path,
)
from katalon.services.metadata_mapping_service import extract_values

MODS_NS = "http://www.loc.gov/mods/v3"

# Pragmatic subset of MODS 3.x (the descriptive part METS wraps in dmdSec/mdWrap/xmlData).
# Extend via a metadata_formats DB row (config={"targets": [...]}) rather than forking this class.
MODS_TARGETS = {
    "mods:titleInfo/mods:title",
    "mods:name/mods:namePart",
    "mods:typeOfResource",
    "mods:originInfo/mods:dateCreated",
    "mods:abstract",
    "mods:accessCondition",
    "mods:identifier",
    "mods:language/mods:languageTerm",
}


class MetsModsFormat(MetadataFormat):
    key = "mets_mods"
    label = "METS/MODS"
    targets = MODS_TARGETS
    schema_url = "http://www.loc.gov/standards/mods/v3/mods-3-8.xsd"
    namespace = MODS_NS

    def capabilities(self) -> ExportProfileCapabilities:
        targets_def = [
            ("mods:titleInfo/mods:title", "title", "Titel", "Title", "Haupttitel des Objekts", "Main title of the resource", True),
            ("mods:name/mods:namePart", "agents", "Name / Akteur", "Name / Agent", "Verfasser, Fotograf oder Urheber", "Name of entity associated with resource", False),
            ("mods:typeOfResource", "type", "Ressourcentyp", "Type of Resource", "Gattung (z. B. still image, text)", "Nature of resource genre", False),
            ("mods:originInfo/mods:dateCreated", "dates", "Entstehungsdatum", "Date Created", "Datum der Schöpfung", "Creation date", False),
            ("mods:abstract", "description", "Zusammenfassung / Abstract", "Abstract", "Kurzbeschreibung oder Zusammenfassung", "Summary or description", False),
            ("mods:accessCondition", "rights", "Nutzungsbedingungen", "Access Condition", "Rechte- oder Lizenzangabe", "Rights or licensing information", False),
            ("mods:identifier", "identification", "Identifikator", "Identifier", "Signatur oder persistente ID", "Identifier string", False),
            ("mods:language/mods:languageTerm", "language", "Sprache", "Language", "ISO 639 Sprachcode", "Language term", False),
        ]
        caps = [
            ExportTargetCapability(
                key=key,
                group=group,
                label=LocalizedText(de=lde, en=len_),
                help=LocalizedText(de=hde, en=hen),
                source_kinds={SourceKind.FIELD, SourceKind.RELATION} if group == "agents" else {SourceKind.FIELD, SourceKind.RECORD, SourceKind.CONSTANT},
                required=req,
            )
            for key, group, lde, len_, hde, hen, req in targets_def
        ]
        return ExportProfileCapabilities(
            format_key=self.key,
            profile_id="mets_mods_core",
            profile_version="3.8",
            label=LocalizedText(de="METS/MODS Kernprofil (3.8)", en="METS/MODS Core Profile (3.8)"),
            targets=caps,
            validators=[ValidatorDependency(name="LOC MODS 3.8 Schema", version="3.8", available=True)],
        )
    def render(
        self, hit: dict[str, Any], mappings: CompiledMappingSet | dict[str, list[str]]
    ) -> ET.Element:
        record_id = hit["_id"]
        src = hit["_source"]
        record_type = src.get("record_type", "")

        root = ET.Element("mods:mods", {"xmlns:mods": MODS_NS, "ID": str(record_id)})

        mapping_set = (
            mappings
            if isinstance(mappings, CompiledMappingSet)
            else CompiledMappingSet.from_legacy_dict(self.key, record_type, mappings)
        )

        for rule in mapping_set.rules:
            if not rule.is_enabled:
                continue
            field_name = rule.field_name
            if not field_name:
                continue
            for value in extract_values(src, field_name):
                if prefix := rule.settings.get("prefix"):
                    value = f"{prefix}{value}"
                if rule.target_key in self.targets:
                    append_path(root, rule.target_key, value)
        return root
