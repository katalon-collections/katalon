# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

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
from katalon.integrations.mets.builder import METS_NS, MODS_NS, build_mets_element

# 20 Top-Level Elements in MODS (Library of Congress specification)
CORE_MODS_TARGETS = {
    "mods:titleInfo/mods:title",
    "mods:name/mods:namePart",
    "mods:typeOfResource",
    "mods:originInfo/mods:dateCreated",
    "mods:abstract",
    "mods:accessCondition",
    "mods:identifier",
    "mods:language/mods:languageTerm",
}

OPTIONAL_MODS_TARGETS = {
    "mods:genre",
    "mods:tableOfContents",
    "mods:physicalDescription/mods:extent",
    "mods:targetAudience",
    "mods:note",
    "mods:subject/mods:topic",
    "mods:classification",
    "mods:relatedItem/mods:titleInfo/mods:title",
    "mods:location/mods:physicalLocation",
    "mods:part/mods:detail/mods:number",
    "mods:extension",
    "mods:recordInfo/mods:recordIdentifier",
}

ALL_MODS_TARGETS = CORE_MODS_TARGETS | OPTIONAL_MODS_TARGETS


class MetsModsFormat(MetadataFormat):
    key = "mets_mods"
    label = "METS/MODS"
    targets = ALL_MODS_TARGETS
    schema_url = "http://www.loc.gov/standards/mods/v3/mods-3-8.xsd"
    namespace = MODS_NS

    def capabilities(self) -> ExportProfileCapabilities:
        # 8 Core targets (displayed by default in mapping workspace)
        core_targets_def = [
            (
                "mods:titleInfo/mods:title",
                "title",
                "Titel",
                "Title",
                "Haupttitel des Objekts",
                "Main title of the resource",
                True,
                {SourceKind.FIELD, SourceKind.RECORD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:name/mods:namePart",
                "agents",
                "Name / Akteur",
                "Name / Agent",
                "Verfasser, Fotograf oder Urheber",
                "Name of entity associated with resource",
                False,
                {SourceKind.FIELD, SourceKind.RELATION, SourceKind.CONSTANT},
                {"text", "relation"},
                "many",
            ),
            (
                "mods:typeOfResource",
                "type",
                "Ressourcentyp",
                "Type of Resource",
                "Gattung (z. B. still image, text)",
                "Nature of resource genre",
                False,
                {SourceKind.FIELD, SourceKind.RECORD, SourceKind.CONSTANT},
                {"text"},
                "one",
            ),
            (
                "mods:originInfo/mods:dateCreated",
                "dates",
                "Entstehungsdatum",
                "Date Created",
                "Datum der Schöpfung",
                "Creation date",
                False,
                {SourceKind.FIELD, SourceKind.RECORD, SourceKind.CONSTANT},
                {"text", "date"},
                "many",
            ),
            (
                "mods:abstract",
                "description",
                "Zusammenfassung / Abstract",
                "Abstract",
                "Kurzbeschreibung oder Zusammenfassung",
                "Summary or description",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:accessCondition",
                "rights",
                "Objekt- / Medienlizenz",
                "Object / Media License",
                "Nutzungsrechte und Lizenz des Objekts bzw. der Digitalisate (z. B. CC-BY, Gemeinfreiheit). Befüllt METS amdSec dv:rights und mods:accessCondition – unterscheidet sich von den Rechten am Metadatensatz.",
                "Usage rights and license for the object or digital media (e.g. CC-BY, Public Domain). Fills METS amdSec dv:rights and mods:accessCondition – distinct from metadata record rights.",
                False,
                {SourceKind.FIELD, SourceKind.MEDIA, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:identifier",
                "identification",
                "Identifikator",
                "Identifier",
                "Signatur oder persistente ID",
                "Identifier string",
                False,
                {SourceKind.FIELD, SourceKind.RECORD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:language/mods:languageTerm",
                "language",
                "Sprache",
                "Language",
                "ISO 639 Sprachcode",
                "Language term",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
        ]

        # 12 Optional Top-Level targets (selectable via "+ Weiteres MODS-Element..." dropdown)
        optional_targets_def = [
            (
                "mods:genre",
                "classification",
                "Genre / Gattung",
                "Genre",
                "Gattungsbegriff oder Werkkategorie",
                "Genre term or category",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:tableOfContents",
                "description",
                "Inhaltsverzeichnis",
                "Table of Contents",
                "Inhaltsverzeichnis oder Gliederung",
                "Table of contents or breakdown",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:physicalDescription/mods:extent",
                "description",
                "Physische Beschreibung / Umfang",
                "Physical Description / Extent",
                "Umfang, Format oder Materialangabe",
                "Extent, format, or physical details",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:targetAudience",
                "description",
                "Zielgruppe",
                "Target Audience",
                "Zielpublikum der Ressource",
                "Intended audience of resource",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:note",
                "description",
                "Anmerkung / Note",
                "Note",
                "Allgemeine Anmerkungen oder Hinweise mit optionalem Notiztyp (z. B. biographical, ownership)",
                "General note or remarks with optional type attribute (e.g. biographical, ownership)",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
                "mods_note",
            ),
            (
                "mods:subject/mods:topic",
                "classification",
                "Thema / Schlagwort",
                "Subject / Topic",
                "Sachschlagwort oder Themenbegriff",
                "Subject topic or keyword",
                False,
                {SourceKind.FIELD, SourceKind.RELATION, SourceKind.CONSTANT},
                {"text", "relation"},
                "many",
            ),
            (
                "mods:classification",
                "classification",
                "Klassifikation",
                "Classification",
                "Klassifikationsnummer oder Systematik",
                "Classification code or notation",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:relatedItem/mods:titleInfo/mods:title",
                "relations",
                "Verknüpftes Werk / Objekt",
                "Related Item",
                "Titel eines übergeordneten oder verwandten Werks",
                "Title of a related or host resource",
                False,
                {SourceKind.FIELD, SourceKind.RELATION, SourceKind.CONSTANT},
                {"text", "relation"},
                "many",
            ),
            (
                "mods:location/mods:physicalLocation",
                "identification",
                "Standort / Verwahrort",
                "Location / Physical Location",
                "Institutioneller Verwahr- oder Lagerort",
                "Physical repository or holding location",
                False,
                {SourceKind.FIELD, SourceKind.RELATION, SourceKind.CONSTANT},
                {"text", "relation"},
                "many",
            ),
            (
                "mods:part/mods:detail/mods:number",
                "description",
                "Teilangabe / Band",
                "Part / Volume",
                "Band- oder Teilnummerierung",
                "Part or volume number",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:extension",
                "description",
                "Erweiterung / Extension",
                "Extension",
                "Benutzerdefinierte XML- oder Zusatzdaten",
                "Custom extension data",
                False,
                {SourceKind.FIELD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
            (
                "mods:recordInfo/mods:recordIdentifier",
                "identification",
                "Datensatz-Identifikator",
                "Record Info / Identifier",
                "Identifikator des Metadatensatzes",
                "Metadata record identifier",
                False,
                {SourceKind.FIELD, SourceKind.RECORD, SourceKind.CONSTANT},
                {"text"},
                "many",
            ),
        ]

        caps: list[ExportTargetCapability] = []
        for key, group, lde, len_, hde, hen, req, sk, ft, card in core_targets_def:
            caps.append(
                ExportTargetCapability(
                    key=key,
                    group=group,
                    label=LocalizedText(de=lde, en=len_),
                    help=LocalizedText(de=hde, en=hen),
                    source_kinds=sk,
                    accepted_field_types=ft,
                    cardinality=card,
                    required=req,
                    is_core=True,
                )
            )
        for key, group, lde, len_, hde, hen, req, sk, ft, card, *extra in optional_targets_def:
            editor_kind = str(extra[0]) if extra else "default"
            caps.append(
                ExportTargetCapability(
                    key=key,
                    group=group,
                    label=LocalizedText(de=lde, en=len_),
                    help=LocalizedText(de=hde, en=hen),
                    source_kinds=sk,
                    accepted_field_types=ft,
                    cardinality=card,
                    required=req,
                    editor_kind=editor_kind,
                    is_core=False,
                )
            )

        return ExportProfileCapabilities(
            format_key=self.key,
            profile_id="mets_mods_core",
            profile_version="3.8",
            label=LocalizedText(de="METS/MODS Kernprofil (3.8)", en="METS/MODS Core Profile (3.8)"),
            targets=caps,
            validators=[ValidatorDependency(name="LOC MODS 3.8 Schema", version="3.8", available=True)],
        )

    def validate_mapping(self, mapping_set: CompiledMappingSet) -> list[MappingDiagnostic]:
        """Validate that the METS/MODS core profile has its required mapped values."""
        diagnostics: list[MappingDiagnostic] = []
        for rule in mapping_set.rules:
            if rule.target_key in self.targets or rule.target_key.startswith("mods:note/"):
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
        if "mods:titleInfo/mods:title" not in mapped_targets:
            diagnostics.append(
                MappingDiagnostic(
                    code="required_target_missing",
                    message="Pflichtziel für METS/MODS fehlt: 'mods:titleInfo/mods:title'.",
                    target_key="mods:titleInfo/mods:title",
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
        return build_mets_element(ctx, mapping_set, mapping_set.institution_config)

    def render_batch_envelope(self) -> tuple[str, str]:
        header = f'<?xml version="1.0" encoding="UTF-8"?>\n<mets:metsCollection xmlns:mets="{METS_NS}">\n'
        return (header, "</mets:metsCollection>\n")

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
        return build_mets_element(ctx, mapping_set, mapping_set.institution_config)
