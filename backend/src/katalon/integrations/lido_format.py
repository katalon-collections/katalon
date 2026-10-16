# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.lido.builder import (
    EVENT_SUBTARGETS,
    GML_NS,
    LIDO_NS,
    MEASUREMENTS_SET_TARGET,
    RECORD_RIGHTS_CREDIT_TARGET,
    RIGHTS_WORK_CREDIT_TARGET,
    SCHEMA_LOC,
    SUPPORTED_LIDO_VERSIONS,
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

# Pragmatic subset of LIDO 1.0 covering the fields catalogers map most often.
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
    MEASUREMENTS_SET_TARGET,
    RIGHTS_WORK_CREDIT_TARGET,
    RECORD_RIGHTS_CREDIT_TARGET,
}


def _setting(de: str, en: str, help_de: str, help_en: str, **extra: object) -> dict[str, object]:
    """One entry of a target's settings_schema (rendered by the admin mapping editor)."""
    return {
        "type": "string",
        "title": {"de": de, "en": en},
        "description": {"de": help_de, "en": help_en},
        **extra,
    }


_TYPE_SETTING = _setting(
    "Typ (lido:type)",
    "Type (lido:type)",
    "Freier Begriff oder Terminologie-URI für das Attribut lido:type.",
    "Free term or terminology URI for the lido:type attribute.",
)
_LANG_SETTING = _setting(
    "Sprache des Begriffs",
    "Term language",
    "Sprachcode für xml:lang am Begriff (z. B. en), wenn er von der Datensatzsprache abweicht.",
    "Language code for xml:lang on the term (e.g. en) if it differs from the record language.",
)

# settings_schema per target key (properties of MappingSpec.settings).
TARGET_SETTINGS: dict[str, dict[str, object]] = {
    "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType": {
        "properties": {"type": _TYPE_SETTING, "lang": _LANG_SETTING},
    },
    "lido:objectClassificationWrap/lido:classificationWrap/lido:classification": {
        "properties": {"type": _TYPE_SETTING, "lang": _LANG_SETTING},
    },
    "lido:objectIdentificationWrap/lido:inscriptionsWrap/lido:inscriptions/lido:inscriptionTranscription": {
        "properties": {
            "description": _setting(
                "Inschriftbeschreibung",
                "Inscription description",
                "Text für inscriptionDescription, z. B. „gedruckt, Vorderseite“.",
                "Text for inscriptionDescription, e.g. 'printed, front'.",
            ),
        },
    },
    "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue": {
        "properties": {"type": _TYPE_SETTING},
    },
    MEASUREMENTS_SET_TARGET: {
        "properties": {
            "measurement_type": _setting(
                "Maßart",
                "Measurement type",
                "measurementType, z. B. „Kürzere Seite“.",
                "measurementType, e.g. 'shorter side'.",
            ),
            "unit": _setting(
                "Einheit (Standard)",
                "Unit (default)",
                "Einheit, falls der Wert keine enthält (z. B. cm).",
                "Unit used when the value carries none (e.g. cm).",
            ),
        },
    },
    "lido:objectRelationWrap/lido:subjectWrap/lido:subjectSet/lido:subject/lido:subjectConcept/lido:term": {
        "properties": {"lang": _LANG_SETTING},
    },
    "lido:objectRelationWrap/lido:relatedWorksWrap/lido:relatedWorkSet/lido:relatedWork/lido:displayObject": {
        "properties": {
            "rel_type": _setting(
                "Beziehungsart",
                "Relation type",
                "Begriff für relatedWorkRelType, z. B. „Teil von (Serie)“.",
                "Term for relatedWorkRelType, e.g. 'part of (series)'.",
            ),
        },
    },
}

# settings_schema of the per-event sub-targets lido:events/{id}/{sub}.
EVENT_TARGET_SETTINGS: dict[str, dict[str, object]] = {
    "actor": {
        "properties": {
            "role": _setting("Rolle", "Role", "Begriff für roleActor/term.", "Term for roleActor/term."),
            "role_uri": _setting(
                "Rollen-URI", "Role URI", "Optionale URI für roleActor/conceptID.",
                "Optional URI for roleActor/conceptID.",
            ),
        },
    },
    "date": {
        "properties": {
            "label_field": _setting(
                "Feld für Datumsart",
                "Date type field",
                "Feld, dessen Wert als lido:label an displayDate steht (z. B. Datierungsart).",
                "Field whose value becomes lido:label on displayDate (e.g. dating method).",
                widget="field",
            ),
        },
    },
    # The editor offers source_config.via (second relation step) for these targets.
    "place": {"properties": {}, "supports_via": True},
    "materials_tech_term": {
        "properties": {
            "kind": _setting(
                "Art", "Kind", "material oder technique (lido00132 / lido00131).",
                "material or technique (lido00132 / lido00131).", enum=["material", "technique"],
            ),
            "lang": _LANG_SETTING,
        },
    },
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
            (
                MEASUREMENTS_SET_TARGET,
                "identification",
                "Maß (strukturiert)",
                "Measurement (structured)",
                "Ein Maß mit Art und Einheit: „9,2 cm“ wird zu measurementValue 9.2 und measurementUnit cm. Nicht lesbare Werte erscheinen nur als Anzeige-Maß.",
                "One measurement with type and unit: '9,2 cm' becomes measurementValue 9.2 and measurementUnit cm. Unreadable values only appear as display measurement.",
                False,
                {SourceKind.FIELD},
            ),
            (
                RIGHTS_WORK_CREDIT_TARGET,
                "rights",
                "Rechte am Objekt: Credit Line",
                "Object rights: credit line",
                "Rechte- oder Herkunftsvermerk zum Objekt (z. B. Schenkung).",
                "Rights or provenance note for the object (e.g. donation).",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
            ),
            (
                RECORD_RIGHTS_CREDIT_TARGET,
                "rights",
                "Rechte am Datensatz: Credit Line",
                "Record rights: credit line",
                "Vermerk zu den Metadaten, z. B. „Erschließung gefördert durch …“. Steht nach rightsType und rightsHolder.",
                "Note on the metadata, e.g. 'cataloguing funded by …'. Placed after rightsType and rightsHolder.",
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
                cardinality="many",
                settings_schema=TARGET_SETTINGS.get(key, {}),
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
            template_settings=EVENT_TARGET_SETTINGS,
        )
    def validate_mapping(self, mapping_set: CompiledMappingSet) -> list[MappingDiagnostic]:
        """Validate that the LIDO core has its required mapped values."""
        diagnostics: list[MappingDiagnostic] = []
        for rule in mapping_set.rules:
            if rule.target_key in self.targets:
                continue
            if rule.target_key.startswith("lido:events/"):
                parts = rule.target_key.split("/")
                if len(parts) == 3 and parts[2] in EVENT_SUBTARGETS:
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
        version = str((mapping_set.institution_config or {}).get("lido_version") or "1.0")
        if version not in SUPPORTED_LIDO_VERSIONS:
            diagnostics.append(
                MappingDiagnostic(
                    code="unsupported_lido_version",
                    message=f"LIDO-Version {version} wird nicht unterstützt (nur 1.0).",
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
