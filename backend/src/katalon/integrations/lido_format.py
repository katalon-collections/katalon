# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.lido.builder import LIDO_NS, build_lido_element
from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportProfileCapabilities,
    ExportRecordContext,
    ExportTargetCapability,
    LocalizedText,
    MappingDiagnostic,
    MetadataFormat,
    SourceKind,
    ValidatorDependency,
)

# Pragmatic subset of LIDO 1.1 covering the fields catalogers map most often.
LIDO_TARGETS = {
    "lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
    "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
    "lido:objectIdentificationWrap/lido:inscriptionsWrap/lido:inscriptions/lido:inscriptionTranscription",
    "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue",
    "lido:objectIdentificationWrap/lido:objectMeasurementsWrap/lido:objectMeasurementsSet/lido:displayObjectMeasurements",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventPlace/lido:displayPlace",
    "lido:objectRelationWrap/lido:subjectWrap/lido:subjectSet/lido:subject/lido:subjectConcept/lido:term",
    "lido:rightsWorkWrap/lido:rightsWorkSet/lido:rightsType/lido:term",
    "lido:administrativeMetadata/lido:resourceWrap/lido:resourceSet/lido:resourceRepresentation/lido:linkResource",
}


class LidoFormat(MetadataFormat):
    key = "lido"
    label = "LIDO"
    targets = LIDO_TARGETS
    schema_url = "http://www.lido-schema.org/schema/v1.0/lido-v1.0.xsd"
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
            profile_id="lido_bpk",
            profile_version="1.0",
            label=LocalizedText(de="LIDO 1.0 (BPK / DDB)", en="LIDO 1.0 (BPK / Europeana)"),
            targets=caps,
            validators=[ValidatorDependency(name="LIDO XML Schema 1.0", version="1.0", available=True)],
        )
    def validate_mapping(self, mapping_set: CompiledMappingSet) -> list[MappingDiagnostic]:
        """Validate mapping set against targets and verify schema compliance."""
        diagnostics = super().validate_mapping(mapping_set)
        return diagnostics

    def render(
        self,
        hit: ExportRecordContext | dict[str, Any],
        mappings: CompiledMappingSet | dict[str, list[str]],
    ) -> ET.Element:
        ctx = hit if isinstance(hit, ExportRecordContext) else ExportRecordContext.from_hit(hit)
        mapping_set = (
            mappings
            if isinstance(mappings, CompiledMappingSet)
            else CompiledMappingSet.from_legacy_dict(self.key, ctx.record.record_type, mappings)
        )
        return build_lido_element(ctx, mapping_set, mapping_set.institution_config)
