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
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventType/lido:term",
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
                "Gattung oder Art des Werks (z. B. Fotografie, Gemälde)",
                "Nature or category of the work (e.g. Photograph, Painting)",
                True,
                {SourceKind.FIELD, SourceKind.CONSTANT},
            ),
            (
                "lido:objectIdentificationWrap/lido:inscriptionsWrap/lido:inscriptions/lido:inscriptionTranscription",
                "identification",
                "Inschrift",
                "Inscription",
                "Transkription einer Inschrift oder Aufschrift",
                "Transcription of an inscription or marking",
                False,
                {SourceKind.FIELD},
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
                "lido:objectIdentificationWrap/lido:objectMeasurementsWrap/lido:objectMeasurementsSet/lido:displayObjectMeasurements",
                "identification",
                "Maße",
                "Measurements",
                "Maßangabe des Objekts",
                "Measurement statement for the object",
                False,
                {SourceKind.FIELD},
            ),
            (
                "lido:eventWrap/lido:eventSet/lido:event/lido:eventType/lido:term",
                "events",
                "Ereignistyp",
                "Event Type",
                "Art des Ereignisses, etwa Herstellung oder Erwerb",
                "Nature of the event, such as production or acquisition",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
            ),
            (
                "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate",
                "events",
                "Ereignisdatum (Anzeige)",
                "Event Date (Display)",
                "Lesbare Datumsangabe für das Ereignis",
                "Human-readable date statement for the event",
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
                "lido:objectRelationWrap/lido:subjectWrap/lido:subjectSet/lido:subject/lido:subjectConcept/lido:term",
                "relations",
                "Thema / Schlagwort",
                "Subject / Keyword",
                "Sachbegriff, Thema oder Schlagwort",
                "Subject concept, topic, or keyword",
                False,
                {SourceKind.FIELD},
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
            (
                "lido:administrativeMetadata/lido:resourceWrap/lido:resourceSet/lido:resourceRepresentation/lido:linkResource",
                "media",
                "Digitale Ressource",
                "Digital Resource",
                "Öffentliche Medien-URL",
                "Public media URL",
                False,
                {SourceKind.MEDIA},
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
            profile_version="1.0",
            label=LocalizedText(de="LIDO 1.0", en="LIDO 1.0"),
            targets=caps,
            validators=[ValidatorDependency(name="LIDO XML Schema 1.0", version="1.0", available=True)],
        )
    def validate_mapping(self, mapping_set: CompiledMappingSet) -> list[MappingDiagnostic]:
        """Validate that the LIDO core has its required mapped values."""
        diagnostics = super().validate_mapping(mapping_set)
        if diagnostics:
            return diagnostics
        mapped_targets = {rule.target_key for rule in mapping_set.rules if rule.is_enabled}
        for target in (
            "lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
            "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
        ):
            if target not in mapped_targets:
                diagnostics.append(
                    MappingDiagnostic(
                        code="required_target_missing",
                        message=f"Pflichtziel für LIDO fehlt: '{target}'.",
                        target_key=target,
                    )
                )
        event_targets = {
            "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue",
            "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate",
            "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate",
        }
        event_type_target = "lido:eventWrap/lido:eventSet/lido:event/lido:eventType/lido:term"
        if event_targets & mapped_targets and event_type_target not in mapped_targets:
            diagnostics.append(
                MappingDiagnostic(
                    code="event_type_missing",
                    message="Ein LIDO-Ereignis benötigt einen gemappten Ereignistyp.",
                    target_key=event_type_target,
                )
            )
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
