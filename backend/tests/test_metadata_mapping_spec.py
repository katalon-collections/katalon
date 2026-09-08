# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.core.models import ExportMappingRule, ExportMappingSet
from katalon.integrations.jsonld_format import JsonLdFormat
from katalon.integrations.lido_format import LidoFormat
from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    MappingSpec,
    SourceKind,
)
from katalon.integrations.mets_mods_format import MetsModsFormat
from katalon.integrations.oai_dc_format import OaiDcFormat
from katalon.services import metadata_format_service, metadata_mapping_service


def _sample_hit() -> dict:
    return {
        "_id": "550e8400-e29b-41d4-a716-446655440000",
        "_source": {
            "record_type": "object",
            "title": "Historische Ansicht",
            "idno": "POSTCARD-42",
            "metadata": {
                "photographer": "Max Mustermann",
                "notes": "Gelaufen am 12.05.1910",
                "tags": ["Postkarte", "Osnabrück"],
            },
        },
    }


# ---------------------------------------------------------------------------
# MappingSpec & CompiledMappingSet Unit Tests
# ---------------------------------------------------------------------------


def test_mappingspec_creation_and_field_name_property() -> None:
    rule_id = uuid.uuid4()
    field_rule = MappingSpec(
        rule_key=rule_id,
        source_kind=SourceKind.FIELD,
        source_config={"field_name": "photographer", "field_type": "text"},
        target_key="dc:creator",
        settings={"prefix": "Foto: "},
        sort_order=5,
        is_enabled=True,
    )
    assert field_rule.rule_key == rule_id
    assert field_rule.field_name == "photographer"
    assert field_rule.settings["prefix"] == "Foto: "

    relation_rule = MappingSpec(
        source_kind=SourceKind.RELATION,
        source_config={"relation_type": "photographer"},
        target_key="lido:eventActor",
    )
    assert relation_rule.field_name is None


def test_compiled_mapping_set_from_legacy_dict_and_dict_protocol() -> None:
    legacy = {
        "title": ["dc:title"],
        "photographer": ["dc:creator", "dc:contributor"],
    }
    cms = CompiledMappingSet.from_legacy_dict("oai_dc", "object", legacy)
    assert cms.format_key == "oai_dc"
    assert cms.record_type == "object"
    assert len(cms.rules) == 3

    # Check by_field
    bf = cms.by_field()
    assert bf["title"] == ["dc:title"]
    assert bf["photographer"] == ["dc:creator", "dc:contributor"]

    # Check by_target
    bt = cms.by_target()
    assert len(bt["dc:creator"]) == 1
    assert bt["dc:creator"][0].field_name == "photographer"

    # Dict-like protocol compatibility
    assert "title" in cms
    assert cms["title"] == ["dc:title"]
    assert cms.get("photographer") == ["dc:creator", "dc:contributor"]
    assert cms.get("unknown") is None
    assert set(cms.keys()) == {"title", "photographer"}
    assert len(cms) == 2
    assert list(cms) == ["title", "photographer"]


# ---------------------------------------------------------------------------
# Format Adapters with CompiledMappingSet: settings & sort_order
# ---------------------------------------------------------------------------


def test_oai_dc_render_with_settings_and_sort_order() -> None:
    fmt = OaiDcFormat()
    hit = _sample_hit()

    cms = CompiledMappingSet(
        format_key="oai_dc",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "photographer"},
                target_key="dc:creator",
                settings={"prefix": "Fotograf: "},
                sort_order=1,
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="dc:title",
                settings={},
                sort_order=2,
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "notes"},
                target_key="dc:description",
                settings={},
                sort_order=3,
                is_enabled=False,  # Disabled rule must be ignored
            ),
        ],
    )

    el = fmt.render(hit, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    assert "<dc:creator>Fotograf: Max Mustermann</dc:creator>" in xml_str
    assert "<dc:title>Historische Ansicht</dc:title>" in xml_str
    assert "Gelaufen am" not in xml_str  # Disabled rule not present


def test_lido_render_with_settings_and_rules() -> None:
    fmt = LidoFormat()
    hit = _sample_hit()

    cms = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
                settings={"prefix": "Titel: "},
                sort_order=1,
            ),
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "notes"},
                target_key="lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue",
                settings={},
                sort_order=2,
                is_enabled=False,
            ),
        ],
    )

    el = fmt.render(hit, cms)
    xml_str = ET.tostring(el, encoding="unicode")

    assert "Titel: Historische Ansicht" in xml_str
    assert "Gelaufen am" not in xml_str


def test_mets_mods_render_with_settings_and_rules() -> None:
    fmt = MetsModsFormat()
    hit = _sample_hit()

    cms = CompiledMappingSet(
        format_key="mets_mods",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="mods:titleInfo/mods:title",
                settings={"prefix": "[Karte] "},
            ),
        ],
    )

    el = fmt.render(hit, cms)
    xml_str = ET.tostring(el, encoding="unicode")
    assert "[Karte] Historische Ansicht" in xml_str


def test_jsonld_render_with_settings_and_rules() -> None:
    fmt = JsonLdFormat()
    hit = _sample_hit()

    cms = CompiledMappingSet(
        format_key="json_ld",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "photographer"},
                target_key="crm:P14_carried_out_by",
                settings={"prefix": "Person: "},
            ),
        ],
    )

    el = fmt.render(hit, cms)
    assert el.text is not None
    assert "Person: Max Mustermann" in el.text


# ---------------------------------------------------------------------------
# MetadataFormat.validate_mapping Tests
# ---------------------------------------------------------------------------


def test_validate_mapping_valid_and_invalid_targets() -> None:
    fmt = OaiDcFormat()

    valid_rule = MappingSpec(
        rule_key=uuid.uuid4(),
        source_kind=SourceKind.FIELD,
        source_config={"field_name": "title"},
        target_key="dc:title",
    )
    invalid_rule = MappingSpec(
        rule_key=uuid.uuid4(),
        source_kind=SourceKind.FIELD,
        source_config={"field_name": "unknown"},
        target_key="invalid:target",
    )

    cms = CompiledMappingSet(
        format_key="oai_dc",
        record_type="object",
        rules=[valid_rule, invalid_rule],
    )

    diagnostics = fmt.validate_mapping(cms)
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert diag.code == "invalid_target"
    assert diag.target_key == "invalid:target"
    assert diag.rule_key == invalid_rule.rule_key
    assert diag.level == "error"


# ---------------------------------------------------------------------------
# metadata_mapping_service.get_mapping_index returns CompiledMappingSet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_mapping_index_preserves_settings_and_sort_order() -> None:
    rule_id = uuid.uuid4()
    rule_key = uuid.uuid4()
    set_id = uuid.uuid4()

    mock_set = ExportMappingSet(
        id=set_id,
        format_key="oai_dc",
        profile_id="oai_dc_simple",
        record_type="object",
        name="OAI-DC Object",
        status="published",
        revision=1,
    )
    mock_rule = ExportMappingRule(
        id=rule_id,
        rule_key=rule_key,
        mapping_set_id=set_id,
        source_kind="field",
        source_config={"field_name": "photographer", "field_type": "text"},
        target_key="dc:creator",
        settings={"prefix": "Künstler: "},
        sort_order=10,
        is_enabled=True,
    )
    mock_set.rules = [mock_rule]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_set]
    mock_session.execute.return_value = mock_result

    index = await metadata_mapping_service.get_mapping_index(mock_session, "oai_dc")

    assert "object" in index
    cms = index["object"]
    assert isinstance(cms, CompiledMappingSet)
    assert len(cms.rules) == 1
    rule = cms.rules[0]
    assert rule.rule_key == rule_key
    assert rule.target_key == "dc:creator"
    assert rule.settings == {"prefix": "Künstler: "}
    assert rule.sort_order == 10
    assert rule.field_name == "photographer"

# ---------------------------------------------------------------------------
# Contract tests: All declared targets must be valid and accepted by validate_mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capabilities_contract_for_all_builtins() -> None:
    formats = await metadata_format_service.list_formats()
    assert len(formats) >= 4

    for fmt in formats:
        caps = fmt.capabilities()
        assert caps.format_key == fmt.key
        assert caps.profile_id
        assert caps.profile_version
        assert caps.label.de and caps.label.en
        assert len(caps.targets) > 0

        # Every target declared in capabilities must exist in fmt.targets
        declared_target_keys = {t.key for t in caps.targets}
        for target_key in declared_target_keys:
            assert target_key in fmt.targets, f"{target_key} in capabilities not in {fmt.key}.targets"

        # Check each target capability structure
        for target_cap in caps.targets:
            assert target_cap.key
            assert target_cap.group
            assert target_cap.label.de and target_cap.label.en
            assert len(target_cap.source_kinds) > 0

        # A CompiledMappingSet with all declared targets must pass validate_mapping without errors
        valid_rules = [
            MappingSpec(
                rule_key=uuid.uuid4(),
                source_kind=SourceKind.FIELD,
                source_config={"field_name": f"f_{i}"},
                target_key=t.key,
            )
            for i, t in enumerate(caps.targets)
        ]
        cms_valid = CompiledMappingSet(
            format_key=fmt.key,
            record_type="object",
            rules=valid_rules,
        )
        diags = fmt.validate_mapping(cms_valid)
        assert len(diags) == 0, f"Unexpected diagnostics for valid targets on {fmt.key}: {diags}"

        # An invalid target must produce an 'invalid_target' diagnostic
        cms_invalid = CompiledMappingSet(
            format_key=fmt.key,
            record_type="object",
            rules=[
                MappingSpec(
                    rule_key=uuid.uuid4(),
                    source_kind=SourceKind.FIELD,
                    source_config={"field_name": "f_invalid"},
                    target_key="totally:invalid_target",
                )
            ],
        )
        diags_inv = fmt.validate_mapping(cms_invalid)
        assert len(diags_inv) == 1
        assert diags_inv[0].code == "invalid_target"


@pytest.mark.asyncio
async def test_export_profiles_endpoints() -> None:
    from httpx import ASGITransport, AsyncClient

    from katalon.core.dependencies import get_current_user
    from katalon.core.models import User
    from katalon.main import app

    admin_user = User(
        id=uuid.uuid4(),
        email="admin@example.org",
        hashed_password="hash",
        role="admin",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # GET /v1/export-profiles
            resp = await client.get("/v1/export-profiles")
            assert resp.status_code == 200
            profiles = resp.json()
            assert len(profiles) >= 4
            keys = {p["format_key"] for p in profiles}
            assert {"oai_dc", "lido", "mets_mods", "json_ld"}.issubset(keys)

            # GET /v1/export-profiles/oai_dc/oai_dc_simple
            resp_dc = await client.get("/v1/export-profiles/oai_dc/oai_dc_simple")
            assert resp_dc.status_code == 200
            dc_prof = resp_dc.json()
            assert dc_prof["format_key"] == "oai_dc"
            assert dc_prof["profile_id"] == "oai_dc_simple"
            assert len(dc_prof["targets"]) == 15

            # GET /v1/export-profiles/oai_dc/nonexistent -> 404
            resp_404 = await client.get("/v1/export-profiles/oai_dc/nonexistent")
            assert resp_404.status_code == 404

            # GET /v1/metadata-mappings/formats contains capabilities
            resp_fmts = await client.get("/v1/metadata-mappings/formats")
            assert resp_fmts.status_code == 200
            fmts_data = resp_fmts.json()
            assert any(f["key"] == "lido" and f.get("capabilities") is not None for f in fmts_data)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
