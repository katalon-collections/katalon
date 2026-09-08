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
# Full BPK LIDO 1.0 Rendering & Schema Validation
# ---------------------------------------------------------------------------


def test_bpk_fixture_lido_rendering_and_xsd_validation(bpk_fixture: ExportRecordContext) -> None:
    fmt = LidoFormat()
    cms = CompiledMappingSet(format_key="lido", record_type="object", rules=[])

    el = fmt.render(bpk_fixture, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    # 1. Validate against the bundled official LIDO 1.0 XMLSchema
    errors = validate_lido_xml(xml_str)
    assert errors == [], f"LIDO Schema validation failed: {errors}"

    # 2. Verify root and namespace
    assert "lido:lidoWrap" in el.tag
    assert el.attrib.get("xmlns:lido") == LIDO_NS

    # 3. Verify lidoRecID
    assert "DE-3066--os_ub_0029908" in xml_str

    # 4. Verify category
    assert "E22_Human-Made_Object" in xml_str

    # 5. Verify descriptiveMetadata & classification
    assert "Postkarte" in xml_str
    assert "Historische Bildpostkarten" in xml_str

    # 6. Verify title & inscriptions
    assert "Guerre 1939-1944" in xml_str
    assert "Dessins de Paul Barbier" in xml_str

    # 7. Verify repository info
    assert "Universität Osnabrück" in xml_str
    assert "Osnabrück" in xml_str

    # 8. Verify Event 1: Herstellung
    assert "Herstellung" in xml_str
    assert "Papeterie de Levallois-Clichy" in xml_str
    assert "Paris (F)" in xml_str
    assert "geonames.org/2988507" in xml_str

    # 9. Verify Event 2: Geistige Schöpfung
    assert "Geistige Schöpfung" in xml_str
    assert "Paul Barbier" in xml_str
    assert "118506544" in xml_str

    # 10. Verify Event 3: Gebrauch
    assert "Gebrauch" in xml_str
    assert "<lido:displayDate lido:label=\"Datierung\">1939 bis 1944</lido:displayDate>" in xml_str
    assert "<lido:earliestDate>1939-01-01</lido:earliestDate>" in xml_str
    assert "<lido:latestDate>1944-12-31</lido:latestDate>" in xml_str

    # 11. Verify subjects
    assert "<lido:term>Propaganda</lido:term>" in xml_str
    assert "<lido:term>Zweiter Weltkrieg</lido:term>" in xml_str
    assert "<lido:term>Frankreich</lido:term>" in xml_str

    # 12. Verify administrativeMetadata: rights & public media resource
    assert "rightsWorkWrap" in xml_str
    assert "http://rightsstatements.org/vocab/InC/1.0/" in xml_str
    assert "resourceWrap" in xml_str
    assert "60508_ca_object_representations_media_104088_original.jpg" in xml_str
    assert 'lido:formatResource="image/jpeg"' in xml_str


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
    cms = CompiledMappingSet(format_key="lido", record_type="object", rules=[])

    el = fmt.render(minimal_ctx, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    errors = validate_lido_xml(xml_str)
    assert errors == [], f"Minimal LIDO record failed XSD: {errors}"
    assert "MIN-001" in xml_str
    assert "Minimales Objekt" in xml_str


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
    cms = CompiledMappingSet(format_key="lido", record_type="object", rules=[])

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

    # 1. OAI GetRecord
    get_rec_xml = oaipmh_service.get_record(
        hit,
        base_url="http://test/oai",
        identifier="oai:katalon:object:550e8400",
        prefix="lido",
        metadata_format=fmt,
    )
    assert "<GetRecord>" in get_rec_xml
    assert "<lido:lidoWrap" in get_rec_xml
    assert "DE-3066--os_ub_0029908" in get_rec_xml

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
    )
    assert "<ListRecords>" in list_rec_xml
    assert "<lido:lidoWrap" in list_rec_xml
    assert "Paul Barbier" in list_rec_xml


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
        institution_config={"isil": "DE-9999", "repository_name": "Testarchiv"},
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
    cms = CompiledMappingSet(format_key="lido", record_type="object", rules=[])
    xml_str = ET.tostring(fmt.render(ctx, cms), encoding="unicode")

    assert "rechtemodell" not in xml_str
    assert "098a9aa2-3ec0-4cea-9b25-f49dafa75ab8" not in xml_str
    assert "<lido:conceptID lido:type=\"http://terminology.lido-schema.org/lido00099\" lido:source=\"URI\">CC0 1.0</lido:conceptID>" in xml_str


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
    cms = CompiledMappingSet(format_key="lido", record_type="object", rules=[])
    xml_str = ET.tostring(fmt.render(ctx, cms), encoding="unicode")

    assert "http://creativecommons.org/publicdomain/zero/1.0/" in xml_str
    assert "CC0 1.0" not in xml_str
