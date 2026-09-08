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

LIDO_NS = "http://www.lido-schema.org"

# Pragmatic subset of LIDO 1.1 covering the fields catalogers map most often.
# Extend via a metadata_formats DB row (config={"targets": [...]}) rather than forking this class.
LIDO_TARGETS = {
    "lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
    "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
    "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue",
    "lido:rightsWorkWrap/lido:rightsWorkSet/lido:rightsType/lido:term",
}


class LidoFormat(MetadataFormat):
    key = "lido"
    label = "LIDO"
    targets = LIDO_TARGETS
    schema_url = "http://www.lido-schema.org/schema/v1.1/lido-v1.1.xsd"
    namespace = LIDO_NS

    def capabilities(self) -> ExportProfileCapabilities:
        targets_def = [
            (
                "lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
                "identification",
                "Objekttitel",
                "Object Title",
                "Bevorzugter Titel oder Bezeichnung des Objekts",
                "Preferred title or appellation of the object",
                True,
                {SourceKind.FIELD, SourceKind.RECORD},
            ),
            (
                "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
                "classification",
                "Objektart / Typ",
                "Object / Work Type",
                "Gattung oder Art des Werks (z. B. Postkarte, Gemälde)",
                "Nature or category of the work (e.g. Postcard, Painting)",
                True,
                {SourceKind.FIELD, SourceKind.CONSTANT},
            ),
            (
                "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue",
                "identification",
                "Beschreibung",
                "Description",
                "Freitextbeschreibung oder Erläuterung",
                "Descriptive note or narrative text",
                False,
                {SourceKind.FIELD},
            ),
            (
                "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate",
                "events",
                "Ereignisdatum (Frühestes)",
                "Event Date (Earliest)",
                "Frühestes Datum der Herstellung oder des Gebrauchs",
                "Earliest date of creation, production or use",
                False,
                {SourceKind.FIELD},
            ),
            (
                "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue",
                "events",
                "Beteiligter Akteur / Urheber",
                "Involved Actor / Agent",
                "Künstler, Fotograf, Verlag oder beteiligte Person",
                "Artist, photographer, publisher or involved entity",
                False,
                {SourceKind.FIELD, SourceKind.RELATION},
            ),
            (
                "lido:rightsWorkWrap/lido:rightsWorkSet/lido:rightsType/lido:term",
                "rights",
                "Rechtestatus / Lizenz",
                "Rights Status / License",
                "Rechtsstatus des Werks oder Lizenzangabe (URI/Term)",
                "Rights status or license specification for the work",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
            ),
        ]
        caps = [
            ExportTargetCapability(
                key=key,
                group=group,
                label=LocalizedText(de=lde, en=len_),
                help=LocalizedText(de=hde, en=hen),
                source_kinds=sk,
                required=req,
            )
            for key, group, lde, len_, hde, hen, req, sk in targets_def
        ]
        return ExportProfileCapabilities(
            format_key=self.key,
            profile_id="lido_core",
            profile_version="1.1",
            label=LocalizedText(de="LIDO Kernprofil (1.1)", en="LIDO Core Profile (1.1)"),
            targets=caps,
            validators=[ValidatorDependency(name="LIDO XML Schema", version="1.1", available=True)],
        )
    def render(
        self, hit: dict[str, Any], mappings: CompiledMappingSet | dict[str, list[str]]
    ) -> ET.Element:
        record_id = hit["_id"]
        src = hit["_source"]
        record_type = src.get("record_type", "")

        root = ET.Element("lido:lido", {"xmlns:lido": LIDO_NS})
        ET.SubElement(root, "lido:lidoRecID").text = str(record_id)

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
