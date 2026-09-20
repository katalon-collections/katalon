# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.lido.builder import (
    GML_NS,
    LIDO_NS,
    SCHEMA_LOC,
    XSI_NS,
    build_lido_element,
    missing_required_fields,
)
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
    "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue/short",
    "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue/condition",
    "lido:objectIdentificationWrap/lido:objectMeasurementsWrap/lido:objectMeasurementsSet/lido:displayObjectMeasurements",
    "lido:objectClassificationWrap/lido:classificationWrap/lido:classification",
    "lido:objectRelationWrap/lido:relatedWorksWrap/lido:relatedWorkSet/lido:relatedWork/lido:displayObject",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventType/lido:term",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventPlace/lido:displayPlace",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventMaterialsTech/lido:displayMaterialsTech",
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
                "Gattung oder Art des Werks (z. B. Fotografie, Gemälde). Drei Quellenarten: 1) Subtyp-Normdaten: Der Export übernimmt die AAT/GND/URI-Verknüpfung jedes Subtyps; alle Objekt-Subtypen benötigen dafür Normdaten. 2) Feld aus Objekt: Ein Authority- oder Vokabularfeld für feingliedrige Klassifikation mappen. 3) Freitext: Einen einzelnen lokalen Wert ausgeben.",
                "Nature or category of the work (e.g. Photograph, Painting). Three source types: 1) Subtype authority data: The export uses each subtype's AAT/GND/URI link; every object subtype needs authority data. 2) Object field: Map an authority or vocabulary field for granular classification. 3) Free text: Emit one local value.",
                True,
                {SourceKind.FIELD, SourceKind.CONSTANT, SourceKind.RECORD},
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
                "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue/short",
                "identification",
                "Kurzbeschreibung",
                "Short Description",
                "Kurze Zusammenfassung, separat von der ausführlichen Beschreibung (lido:type=\"brief\")",
                "Brief summary, kept separate from the full description (lido:type=\"brief\")",
                False,
                {SourceKind.FIELD},
            ),
            (
                "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue/condition",
                "identification",
                "Erhaltungszustand",
                "Condition",
                "Zustandsbeschreibung des Objekts (lido:type=\"condition\")",
                "Condition statement for the object (lido:type=\"condition\")",
                False,
                {SourceKind.FIELD},
            ),
            (
                "lido:objectClassificationWrap/lido:classificationWrap/lido:classification",
                "classification",
                "Klassifikation / Sammlung",
                "Classification / Collection",
                "Zusätzlicher Klassifikationsbegriff, etwa Sammlungszugehörigkeit",
                "Additional classification term, such as collection membership",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT, SourceKind.RELATION},
            ),
            (
                "lido:objectRelationWrap/lido:relatedWorksWrap/lido:relatedWorkSet/lido:relatedWork/lido:displayObject",
                "relations",
                "Verwandtes Werk / Teil von",
                "Related Work / Part of",
                "Bezug zu einem anderen Objekt oder Werk (z. B. Teil-von-Beziehung)",
                "Reference to another object or work (e.g. part-of relationship)",
                False,
                {SourceKind.FIELD, SourceKind.RELATION},
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
                "lido:eventWrap/lido:eventSet/lido:event/lido:eventMaterialsTech/lido:displayMaterialsTech",
                "events",
                "Material / Technik",
                "Materials / Technique",
                "Angabe zu Material und Technik (z. B. Öl auf Leinwand, Bronze)",
                "Statement on materials and techniques (e.g. oil on canvas, bronze)",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
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
                cardinality=(
                    "one"
                    if key == "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"
                    else "many"
                ),
                editor_kind=(
                    "lido_work_type"
                    if key == "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"
                    else "default"
                ),
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
        diagnostics: list[MappingDiagnostic] = []
        for rule in mapping_set.rules:
            if rule.target_key in self.targets:
                continue
            if rule.target_key.startswith("lido:events/"):
                parts = rule.target_key.split("/")
                if len(parts) == 3 and parts[2] in {"type", "actor", "date", "earliest_date", "place", "materials_tech"}:
                    continue
            diagnostics.append(
                MappingDiagnostic(
                    code="invalid_target",
                    message=f"Ungültiges {self.label}-Ziel '{rule.target_key}'.",
                    level="error",
                    target_key=rule.target_key,
                    rule_key=rule.rule_key,
                )
            )
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
        work_type_target = "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"
        work_type_rules = [
            rule for rule in mapping_set.rules
            if rule.is_enabled and rule.target_key == work_type_target
        ]
        if len(work_type_rules) > 1:
            diagnostics.append(
                MappingDiagnostic(
                    code="cardinality_exceeded",
                    message="LIDO Objektart / Typ erlaubt nur eine Quellenregel.",
                    target_key=work_type_target,
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

    def required_field_errors(
        self,
        ctx: ExportRecordContext,
        mapping_set: CompiledMappingSet,
    ) -> list[str]:
        return missing_required_fields(ctx, mapping_set)

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

    def render_batch_envelope(self) -> tuple[str, str]:
        header = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<lido:lidoWrap xmlns:lido="{LIDO_NS}" xmlns:gml="{GML_NS}" '
            f'xmlns:xsi="{XSI_NS}" xsi:schemaLocation="{SCHEMA_LOC}">\n'
        )
        return (header, "</lido:lidoWrap>\n")

    def render_batch_item(
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
        return build_lido_element(ctx, mapping_set, mapping_set.institution_config, wrap_envelope=False)
