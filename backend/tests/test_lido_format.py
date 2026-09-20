# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from katalon.integrations.lido.builder import LIDO_NS
from katalon.integrations.lido.validator import validate_lido_xml
from katalon.integrations.lido_format import LidoFormat
from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportRecordContext,
    ExportRecordSummary,
    ExportRelation,
    MappingSpec,
    SourceKind,
)
from katalon.services import oaipmh_service

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def bpk_fixture() -> ExportRecordContext:
    fixture_path = FIXTURES_DIR / "bpk_os_ub_0029908.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    return ExportRecordContext.model_validate(data)


# ---------------------------------------------------------------------------
# Generic LIDO 1.0 Rendering & Schema Validation
# ---------------------------------------------------------------------------


def test_lido_uses_only_explicit_mapping_values(bpk_fixture: ExportRecordContext) -> None:
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "object_type"},
                target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
            ),
            MappingSpec(
                source_kind=SourceKind.CONSTANT,
                source_config={"value": "Herstellung"},
                target_key="lido:eventWrap/lido:eventSet/lido:event/lido:eventType/lido:term",
            ),
            MappingSpec(
                source_kind=SourceKind.RELATION,
                source_config={"relation_type": "creator"},
                target_key=(
                    "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/"
                    "lido:actor/lido:nameActorSet/lido:appellationValue"
                ),
            ),
            MappingSpec(
                source_kind=SourceKind.MEDIA,
                source_config={"property": "url"},
                target_key=(
                    "lido:administrativeMetadata/lido:resourceWrap/lido:resourceSet/"
                    "lido:resourceRepresentation/lido:linkResource"
                ),
            ),
        ],
    )

    el = fmt.render(bpk_fixture, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    # 1. Validate against the bundled official LIDO 1.0 XMLSchema
    errors = validate_lido_xml(xml_str)
    assert errors == [], f"LIDO Schema validation failed: {errors}"

    # 2. Verify root and namespace
    assert "lido:lidoWrap" in el.tag
    assert el.attrib.get("xmlns:lido") == LIDO_NS

    # The LIDO core identifies the record but invents no BPK institution or collection values.
    assert "os_ub_0029908" in xml_str
    assert "DE-3066" not in xml_str
    assert "Historische Bildpostkarten" not in xml_str
    assert "Universität Osnabrück" not in xml_str

    # The structural category is part of the object-only LIDO envelope.
    assert "E22_Human-Made_Object" in xml_str
    assert "Postkarte" in xml_str
    assert "Guerre 1939-1944" in xml_str
    assert "Paul Barbier" in xml_str
    assert "60508_ca_object_representations_media_104088_original.jpg" in xml_str


def test_lido_renders_materials_tech_valid_xsd() -> None:
    ctx = ExportRecordContext(
        record=ExportRecordSummary(
            id="mat-001",
            idno="MAT-001",
            record_type="object",
            title="Gemälde",
            status="public",
        ),
        fields={"title": "Gemälde", "material": "Öl auf Leinwand"},
        relations=[],
        media=[],
    )
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
            ),
            MappingSpec(
                source_kind=SourceKind.CONSTANT,
                source_config={"value": "Gemälde"},
                target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
            ),
            MappingSpec(
                source_kind=SourceKind.CONSTANT,
                source_config={"value": "Herstellung"},
                target_key="lido:events/production/type",
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "material"},
                target_key="lido:events/production/materials_tech",
            ),
        ],
    )

    el = fmt.render(ctx, cms)
    xml_str = ET.tostring(el, encoding="unicode")
    assert "<lido:displayMaterialsTech>Öl auf Leinwand</lido:displayMaterialsTech>" in xml_str

    errors = validate_lido_xml(xml_str)
    assert errors == [], f"MaterialsTech LIDO record failed XSD: {errors}"


def test_lido_batch_envelope_renders_valid_xsd() -> None:
    ctx1 = ExportRecordContext(
        record=ExportRecordSummary(id="b1", idno="B-001", record_type="object", title="Objekt 1"),
        fields={"title": "Objekt 1"},
        relations=[],
        media=[],
    )
    ctx2 = ExportRecordContext(
        record=ExportRecordSummary(id="b2", idno="B-002", record_type="object", title="Objekt 2"),
        fields={"title": "Objekt 2"},
        relations=[],
        media=[],
    )
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
            ),
            MappingSpec(
                source_kind=SourceKind.CONSTANT,
                source_config={"value": "Objekt"},
                target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
            ),
        ],
    )

    header, footer = fmt.render_batch_envelope()
    item1 = fmt.render_batch_item(ctx1, cms)
    item2 = fmt.render_batch_item(ctx2, cms)

    assert "lido:lido" in item1.tag
    assert "lidoWrap" not in item1.tag

    batch_xml = header + ET.tostring(item1, encoding="unicode") + "\n" + ET.tostring(item2, encoding="unicode") + "\n" + footer
    assert "<collection>" not in batch_xml
    assert batch_xml.startswith("<?xml")
    assert "<lido:lidoWrap" in batch_xml
    assert batch_xml.strip().endswith("</lido:lidoWrap>")

    errors = validate_lido_xml(batch_xml)
    assert errors == [], f"Batch LIDO stream failed XSD: {errors}"


# ---------------------------------------------------------------------------
# Minimal Record & Empty Envelopes
# ---------------------------------------------------------------------------


def test_minimal_record_renders_valid_lido_1_0() -> None:
    minimal_ctx = ExportRecordContext(
        record=ExportRecordSummary(
            id="min-001",
            idno="MIN-001",
            record_type="object",
            title="Minimales Objekt",
            status="public",
        ),
        fields={"title": "Minimales Objekt"},
        relations=[],
        media=[],
    )
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "title"}, target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue"),
            MappingSpec(source_kind=SourceKind.CONSTANT, source_config={"value": "Objekt"}, target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"),
        ],
    )

    el = fmt.render(minimal_ctx, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    errors = validate_lido_xml(xml_str)
    assert errors == [], f"Minimal LIDO record failed XSD: {errors}"
    assert "MIN-001" in xml_str
    assert "Minimales Objekt" in xml_str


def test_lido_subtype_source_without_authority_does_not_emit_label_fallback() -> None:
    ctx = ExportRecordContext(
        record=ExportRecordSummary(
            id="no-authority",
            idno="NO-AUTHORITY",
            record_type="object",
            title="Titel",
            status="public",
            target_subtype="Fotografie",
        ),
        fields={"title": "Titel"},
        relations=[],
        media=[],
    )
    mapping = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
            ),
            MappingSpec(
                source_kind=SourceKind.RECORD,
                source_config={"property": "target_subtype"},
                target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
            ),
        ],
    )

    xml = ET.tostring(LidoFormat().render(ctx, mapping), encoding="unicode")

    assert "Fotografie" not in xml

def test_lido_requires_title_and_work_type_mappings() -> None:
    diagnostics = LidoFormat().validate_mapping(
        CompiledMappingSet(format_key="lido", record_type="object", rules=[])
    )

    assert {diagnostic.code for diagnostic in diagnostics} == {"required_target_missing"}
    assert len(diagnostics) == 2

def test_lido_work_type_allows_only_one_source_rule() -> None:
    target = "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"
    capability = next(capability for capability in LidoFormat().capabilities().targets if capability.key == target)
    diagnostics = LidoFormat().validate_mapping(
        CompiledMappingSet(
            format_key="lido",
            record_type="object",
            rules=[
                MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "title"}, target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue"),
                MappingSpec(source_kind=SourceKind.RECORD, source_config={"property": "target_subtype"}, target_key=target),
                MappingSpec(source_kind=SourceKind.CONSTANT, source_config={"value": "Bla"}, target_key=target),
            ],
        )
    )

    assert capability.cardinality == "one"
    assert [diagnostic.code for diagnostic in diagnostics] == ["cardinality_exceeded"]


def test_lido_requires_an_event_type_for_event_mappings() -> None:
    diagnostics = LidoFormat().validate_mapping(
        CompiledMappingSet(
            format_key="lido",
            record_type="object",
            rules=[
                MappingSpec(
                    source_kind=SourceKind.CONSTANT,
                    source_config={"value": "Objekt"},
                    target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
                ),
                MappingSpec(
                    source_kind=SourceKind.FIELD,
                    source_config={"field_name": "title"},
                    target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
                ),
                MappingSpec(
                    source_kind=SourceKind.FIELD,
                    source_config={"field_name": "date"},
                    target_key="lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate",
                ),
            ],
        )
    )

    assert [diagnostic.code for diagnostic in diagnostics] == ["event_type_missing"]


# ---------------------------------------------------------------------------
# HTML Sanitization and XML Escaping
# ---------------------------------------------------------------------------


def test_html_in_fields_is_sanitized_cleanly() -> None:
    ctx = ExportRecordContext(
        record=ExportRecordSummary(
            id="html-001",
            idno="HTML-001",
            record_type="object",
            title="Titel mit <b>HTML</b> & Ampersand",
            status="public",
        ),
        fields={
            "title": "Titel mit <b>HTML</b> & Ampersand",
            "description": "<p>Erster Absatz</p><p>Zweiter Absatz &amp; Sonderzeichen</p><script>alert(1)</script>",
        },
        relations=[],
        media=[],
    )
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "title"}, target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue"),
            MappingSpec(source_kind=SourceKind.CONSTANT, source_config={"value": "Objekt"}, target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"),
            MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "description"}, target_key="lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue"),
        ],
    )

    el = fmt.render(ctx, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    # Document must be valid XML and pass LIDO XSD
    errors = validate_lido_xml(xml_str)
    assert errors == [], f"HTML-sanitized record failed XSD: {errors}"

    # Raw HTML tags must be stripped
    assert "<p>" not in xml_str
    assert "</p>" not in xml_str
    assert "<script>" not in xml_str
    assert "Erster Absatz Zweiter Absatz" in xml_str


# ---------------------------------------------------------------------------
# OAI-PMH Dissemination with LidoFormat
# ---------------------------------------------------------------------------


def test_oai_get_record_and_list_records_with_lido(bpk_fixture: ExportRecordContext) -> None:
    fmt = LidoFormat()
    hit = {
        "_id": bpk_fixture.record.id,
        "_source": {
            "record_type": "object",
            "title": bpk_fixture.record.title,
            "idno": bpk_fixture.record.idno,
            "export_context": bpk_fixture.to_dict(),
        },
    }
    # Title mapping required, else the record is now skipped (empty appellationValue).
    mapping_index = {
        "object": CompiledMappingSet(
            format_key="lido",
            record_type="object",
            rules=[
                MappingSpec(
                    source_kind=SourceKind.FIELD,
                    source_config={"field_name": "title"},
                    target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
                ),
            ],
        ),
    }

    # 1. OAI GetRecord
    get_rec_xml = oaipmh_service.get_record(
        hit,
        base_url="http://test/oai",
        identifier="oai:katalon:object:550e8400",
        prefix="lido",
        metadata_format=fmt,
        mapping_index=mapping_index,
    )
    assert "<GetRecord>" in get_rec_xml
    assert "<lido:lidoWrap" in get_rec_xml
    assert "os_ub_0029908" in get_rec_xml
    assert "DE-3066" not in get_rec_xml

    # 2. OAI ListRecords
    list_rec_xml = oaipmh_service.list_records(
        hits=[hit],
        total=1,
        offset=0,
        set_spec="object",
        from_=None,
        until=None,
        prefix="lido",
        base_url="http://test/oai",
        metadata_format=fmt,
        mapping_index=mapping_index,
    )
    assert "<ListRecords>" in list_rec_xml
    assert "<lido:lidoWrap" in list_rec_xml
    assert "Historische Bildpostkarten" not in list_rec_xml


def test_oai_get_record_missing_required_field_returns_cannot_disseminate(
    bpk_fixture: ExportRecordContext,
) -> None:
    """No title mapping configured -> record must not be exported with an empty appellationValue."""
    fmt = LidoFormat()
    hit = {
        "_id": bpk_fixture.record.id,
        "_source": {
            "record_type": "object",
            "title": bpk_fixture.record.title,
            "idno": bpk_fixture.record.idno,
            "export_context": bpk_fixture.to_dict(),
        },
    }

    xml_str = oaipmh_service.get_record(
        hit,
        base_url="http://test/oai",
        identifier="oai:katalon:object:550e8400",
        prefix="lido",
        metadata_format=fmt,
    )
    assert "cannotDisseminateFormat" in xml_str
    assert "<GetRecord>" not in xml_str

    list_xml = oaipmh_service.list_records(
        hits=[hit],
        total=1,
        offset=0,
        set_spec="object",
        from_=None,
        until=None,
        prefix="lido",
        base_url="http://test/oai",
        metadata_format=fmt,
    )
    assert "noRecordsMatch" in list_xml
    assert "<ListRecords>" not in list_xml


# ---------------------------------------------------------------------------
# Rule-driven actor role & institution_config wiring (Phase 6)
# ---------------------------------------------------------------------------


def test_relation_rule_overrides_default_actor_role(bpk_fixture: ExportRecordContext) -> None:
    """A RELATION rule targeting the actor capability picks the configured relation_type
    and role text instead of the hardcoded BPK defaults."""
    fmt = LidoFormat()
    actor_target = (
        "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole"
        "/lido:actor/lido:nameActorSet/lido:appellationValue"
    )
    mapping_set = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.RELATION,
                source_config={"relation_type": "creator"},
                target_key=actor_target,
                settings={"role": "Fotograf"},
                sort_order=0,
                is_enabled=True,
            )
        ],
    )
    xml_str = ET.tostring(fmt.render(bpk_fixture, mapping_set), encoding="unicode")
    assert "Paul Barbier" in xml_str
    assert "<lido:term>Fotograf</lido:term>" in xml_str


def test_institution_config_reaches_lido_renderer() -> None:
    minimal_ctx = ExportRecordContext(
        record=ExportRecordSummary(id="obj-1", idno="OBJ-1", record_type="object", title="Test"),
    )
    fmt = LidoFormat()
    mapping_set = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[],
        institution_config={"isil": "DE-9999", "institution_name": "Testarchiv", "website": "https://example.test"},
    )
    xml_str = ET.tostring(fmt.render(minimal_ctx, mapping_set), encoding="unicode")
    assert "DE-9999" in xml_str
    assert "Testarchiv" in xml_str


# ---------------------------------------------------------------------------
# Group/vocab field values must not leak their Python repr into XML
# ---------------------------------------------------------------------------


def test_group_vocab_rights_value_extracts_label_not_python_repr() -> None:
    """A group field like `rights` with a nested vocab sub-field
    (`[{"rechtemodell": {"id": ..., "label": "CC0 1.0"}}]`) must render the
    human-readable label, not the stringified Python structure."""
    ctx = ExportRecordContext(
        record=ExportRecordSummary(id="rights-001", idno="RIGHTS-001", record_type="object", title="Test"),
        fields={
            "rights": [
                {"rechtemodell": {"id": "098a9aa2-3ec0-4cea-9b25-f49dafa75ab8", "label": "CC0 1.0"}}
            ],
        },
    )
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "rights"}, target_key="lido:rightsWorkWrap/lido:rightsWorkSet/lido:rightsType/lido:term")],
    )
    xml_str = ET.tostring(fmt.render(ctx, cms), encoding="unicode")

    assert "rechtemodell" not in xml_str
    assert "098a9aa2-3ec0-4cea-9b25-f49dafa75ab8" not in xml_str
    assert "<lido:term>CC0 1.0</lido:term>" in xml_str


def test_group_vocab_value_prefers_uri_over_label() -> None:
    """When a vocab sub-value carries a resolved `uri`, prefer it over the label."""
    ctx = ExportRecordContext(
        record=ExportRecordSummary(id="rights-002", idno="RIGHTS-002", record_type="object", title="Test"),
        fields={
            "rights": [
                {"rechtemodell": {"id": "abc", "label": "CC0 1.0", "uri": "http://creativecommons.org/publicdomain/zero/1.0/"}}
            ],
        },
    )
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "rights"}, target_key="lido:rightsWorkWrap/lido:rightsWorkSet/lido:rightsType/lido:term")],
    )
    xml_str = ET.tostring(fmt.render(ctx, cms), encoding="unicode")

    assert "http://creativecommons.org/publicdomain/zero/1.0/" in xml_str
    assert "CC0 1.0" not in xml_str


def test_lido_multiple_events_rendered_as_separate_event_sets() -> None:
    """Test that multiple events (e.g. Herstellung and Erwerb) produce distinct lido:eventSet blocks."""
    ctx = ExportRecordContext(
        record=ExportRecordSummary(
            id="multi-ev-001",
            idno="POSTCARD-1908",
            record_type="object",
            title="Postkarte Berlin",
        ),
        fields={
            "title": "Postkarte Berlin",
            "herstellungsjahr": "1908",
            "erwerbsjahr": "1985",
            "herstellungsort": "Berlin",
        },
        relations=[
            ExportRelation(
                id="rel-1",
                relation_type="publisher",
                target_type="entity",
                target_id="ent-1",
                target_label="Verlag X",
            ),
            ExportRelation(
                id="rel-2",
                relation_type="donor",
                target_type="entity",
                target_id="ent-2",
                target_label="Familie Schmidt",
            ),
        ],
        media=[],
    )
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        institution_config={
            "lido_events": [
                {"id": "production", "type": "Herstellung", "label_de": "Herstellung", "label_en": "Production"},
                {"id": "acquisition", "type": "Erwerb", "label_de": "Erwerb / Zugang", "label_en": "Acquisition"},
            ]
        },
        rules=[
            MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "title"}, target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue"),
            MappingSpec(source_kind=SourceKind.CONSTANT, source_config={"value": "Postkarte"}, target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"),
            # Event 1: Herstellung
            MappingSpec(source_kind=SourceKind.RELATION, source_config={"relation_type": "publisher"}, settings={"role": "Verlag"}, target_key="lido:events/production/actor"),
            MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "herstellungsjahr"}, target_key="lido:events/production/date"),
            MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "herstellungsort"}, target_key="lido:events/production/place"),
            # Event 2: Erwerb
            MappingSpec(source_kind=SourceKind.RELATION, source_config={"relation_type": "donor"}, settings={"role": "Schenker:in"}, target_key="lido:events/acquisition/actor"),
            MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "erwerbsjahr"}, target_key="lido:events/acquisition/date"),
        ],
    )

    el = fmt.render(ctx, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    errors = validate_lido_xml(xml_str)
    assert errors == [], f"Multi-event LIDO failed XSD: {errors}"

    root = ET.fromstring(xml_str)
    event_sets = root.findall(".//{http://www.lido-schema.org}eventSet")
    assert len(event_sets) == 2, f"Expected 2 eventSet elements, got {len(event_sets)}"

    # Check first event (Herstellung)
    ev1 = event_sets[0]
    assert ev1.find(".//{http://www.lido-schema.org}eventType/{http://www.lido-schema.org}term").text == "Herstellung"
    assert ev1.find(".//{http://www.lido-schema.org}actor/{http://www.lido-schema.org}nameActorSet/{http://www.lido-schema.org}appellationValue").text == "Verlag X"
    assert ev1.find(".//{http://www.lido-schema.org}roleActor/{http://www.lido-schema.org}term").text == "Verlag"
    assert ev1.find(".//{http://www.lido-schema.org}eventDate/{http://www.lido-schema.org}displayDate").text == "1908"
    assert ev1.find(".//{http://www.lido-schema.org}eventPlace/{http://www.lido-schema.org}displayPlace").text == "Berlin"

    # Check second event (Erwerb)
    ev2 = event_sets[1]
    assert ev2.find(".//{http://www.lido-schema.org}eventType/{http://www.lido-schema.org}term").text == "Erwerb"
    assert ev2.find(".//{http://www.lido-schema.org}actor/{http://www.lido-schema.org}nameActorSet/{http://www.lido-schema.org}appellationValue").text == "Familie Schmidt"
    assert ev2.find(".//{http://www.lido-schema.org}roleActor/{http://www.lido-schema.org}term").text == "Schenker:in"
    assert ev2.find(".//{http://www.lido-schema.org}eventDate/{http://www.lido-schema.org}displayDate").text == "1985"


def test_lido_object_work_type_from_subtype_normdaten() -> None:
    """Weg A (Kleine Häuser): Subtyp besitzt AAT-Normdatum, LIDO exportiert conceptID und term."""
    ctx = ExportRecordContext(
        record=ExportRecordSummary(
            id="obj-123",
            idno="INV-2026-01",
            record_type="object",
            target_subtype="gemaelde",
            title="Landschaft bei Weimar",
            subtype_concept_source="aat",
            subtype_concept_id="300033618",
            subtype_concept_uri="http://vocab.getty.edu/aat/300033618",
            subtype_concept_label="Gemälde",
        ),
        fields={"title": "Landschaft bei Weimar"},
        relations=[],
        media=[],
    )
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
            ),
            MappingSpec(
                source_kind=SourceKind.RECORD,
                source_config={"property": "target_subtype"},
                target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
            ),
        ],
    )
    el = fmt.render(ctx, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    errors = validate_lido_xml(xml_str)
    assert errors == [], f"LIDO validation failed: {errors}"

    root = ET.fromstring(xml_str)
    work_type = root.find(".//{http://www.lido-schema.org}objectWorkType")
    assert work_type is not None

    concept_id = work_type.find("{http://www.lido-schema.org}conceptID")
    assert concept_id is not None
    assert concept_id.text == "http://vocab.getty.edu/aat/300033618"
    assert concept_id.attrib.get("{http://www.lido-schema.org}source") == "AAT"
    assert concept_id.attrib.get("{http://www.lido-schema.org}type") == "URI"

    term = work_type.find("{http://www.lido-schema.org}term")
    assert term is not None
    assert term.text == "Gemälde"


def test_lido_object_work_type_from_authority_field() -> None:
    """Weg B (Große Häuser): Dediziertes Authority-Feld (z. B. objektart mit AAT-Concept) gemappt."""
    ctx = ExportRecordContext(
        record=ExportRecordSummary(
            id="obj-456",
            idno="INV-2026-02",
            record_type="object",
            target_subtype="druckgrafik",
            title="Die Melancholie",
        ),
        fields={
            "title": "Die Melancholie",
            "objektart": {
                "source": "aat",
                "id": "300041347",
                "uri": "http://vocab.getty.edu/aat/300041347",
                "label": "copper engravings (visual works)",
            },
        },
        relations=[],
        media=[],
    )
    fmt = LidoFormat()
    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "objektart"},
                target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
            ),
        ],
    )
    el = fmt.render(ctx, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    errors = validate_lido_xml(xml_str)
    assert errors == [], f"LIDO validation failed: {errors}"

    root = ET.fromstring(xml_str)
    work_type = root.find(".//{http://www.lido-schema.org}objectWorkType")
    assert work_type is not None

    concept_id = work_type.find("{http://www.lido-schema.org}conceptID")
    assert concept_id is not None
    assert concept_id.text == "http://vocab.getty.edu/aat/300041347"
    assert concept_id.attrib.get("{http://www.lido-schema.org}source") == "AAT"

    term = work_type.find("{http://www.lido-schema.org}term")
    assert term is not None
    assert term.text == "copper engravings (visual works)"



def test_lido_emits_ddb_record_metadata_defaults() -> None:
    ctx = ExportRecordContext(
        record=ExportRecordSummary(
            id="obj-789",
            idno="INV-2026-03",
            record_type="object",
            title="DDB-Testobjekt",
        )
    )
    mapping_set = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        institution_config={
            "isil": "DE-MUS-123",
            "institution_name": "Testmuseum",
            "portal_host": "https://sammlung.example.test/",
        },
    )

    xml_str = ET.tostring(LidoFormat().render(ctx, mapping_set), encoding="unicode")
    assert validate_lido_xml(xml_str) == []

    root = ET.fromstring(xml_str)
    ns = {"lido": LIDO_NS}
    record_wrap = root.find(".//lido:recordWrap", ns)
    assert record_wrap is not None
    record_id = record_wrap.find("lido:recordID", ns)
    assert record_id is not None
    assert record_id.attrib[f"{{{LIDO_NS}}}type"] == "http://terminology.lido-schema.org/lido00100"
    assert (
        record_wrap.findtext("lido:recordType/lido:conceptID", namespaces=ns)
        == "http://terminology.lido-schema.org/lido00141"
    )
    assert (
        record_wrap.findtext("lido:recordSource/lido:legalBodyID", namespaces=ns)
        == "https://ld.zdb-services.de/resource/organisations/DE-MUS-123"
    )
    assert (
        record_wrap.findtext("lido:recordRights/lido:rightsType/lido:conceptID", namespaces=ns)
        == "https://creativecommons.org/publicdomain/zero/1.0/"
    )
    assert (
        record_wrap.findtext("lido:recordInfoSet/lido:recordInfoLink", namespaces=ns)
        == "https://sammlung.example.test/objects/obj-789"
    )
    assert record_wrap.findtext("lido:recordInfoSet/lido:recordMetadataDate", namespaces=ns)


def test_lido_marks_production_events_with_the_lido_concept() -> None:
    ctx = ExportRecordContext(
        record=ExportRecordSummary(id="obj-production", idno="INV-2026-04", record_type="object"),
        fields={"year": "1900"},
    )
    mapping_set = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "year"},
                target_key="lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate",
            )
        ],
    )

    xml_str = ET.tostring(LidoFormat().render(ctx, mapping_set), encoding="unicode")
    assert validate_lido_xml(xml_str) == []
    root = ET.fromstring(xml_str)
    assert (
        root.findtext(
            ".//{http://www.lido-schema.org}eventType/{http://www.lido-schema.org}conceptID"
        )
        == "http://terminology.lido-schema.org/lido00007"
    )
