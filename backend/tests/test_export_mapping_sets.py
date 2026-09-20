# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.core.dependencies import get_current_user
from katalon.core.models import (
    ExportMappingRule,
    ExportMappingSet,
    PortalConfig,
    RecordSubtype,
    User,
)
from katalon.core.schemas import (
    ExportMappingRuleCreate,
    ExportMappingSetCreate,
    ExportMappingSetUpdate,
)
from katalon.integrations.metadata_format import CompiledMappingSet, MappingSpec, SourceKind
from katalon.main import app
from katalon.services import metadata_mapping_service
from katalon.services.metadata_mapping_service import OptimisticLockError

# ---------------------------------------------------------------------------
# Unit / Service tests for Versioned Mapping Sets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compile_mapping_set_from_model() -> None:
    rule1_id = uuid.uuid4()
    rule1_key = uuid.uuid4()
    rule2_id = uuid.uuid4()
    rule2_key = uuid.uuid4()

    mock_set = ExportMappingSet(
        id=uuid.uuid4(),
        format_key="oai_dc",
        profile_id="oai_dc_simple",
        profile_version="2.0",
        record_type="object",
        name="Test Set",
        status="published",
        revision=1,
        version=1,
    )
    r1 = ExportMappingRule(
        id=rule1_id,
        rule_key=rule1_key,
        mapping_set_id=mock_set.id,
        source_kind="field",
        source_config={"field_name": "title"},
        target_key="dc:title",
        settings={"prefix": "T: "},
        sort_order=1,
        is_enabled=True,
    )
    r2 = ExportMappingRule(
        id=rule2_id,
        rule_key=rule2_key,
        mapping_set_id=mock_set.id,
        source_kind="relation",
        source_config={"relation_type": "creator"},
        target_key="dc:creator",
        settings={},
        sort_order=2,
        is_enabled=False,  # Disabled
    )
    mock_set.rules = [r1, r2]

    cms = metadata_mapping_service.compile_mapping_set(mock_set)
    assert cms.format_key == "oai_dc"
    assert cms.record_type == "object"
    assert len(cms.rules) == 2
    assert cms.rules[0].target_key == "dc:title"
    assert cms.rules[0].source_kind == SourceKind.FIELD
    assert cms.rules[1].target_key == "dc:creator"
    assert cms.rules[1].source_kind == SourceKind.RELATION


@pytest.mark.asyncio
async def test_get_mapping_index_only_reads_published_sets() -> None:
    mock_db = AsyncMock()

    # Create one published set and one draft set
    pub_set = ExportMappingSet(
        id=uuid.uuid4(),
        format_key="oai_dc",
        profile_id="oai_dc_simple",
        record_type="object",
        name="Published OAI-DC",
        status="published",
        revision=1,
    )
    r_pub = ExportMappingRule(
        id=uuid.uuid4(),
        rule_key=uuid.uuid4(),
        mapping_set_id=pub_set.id,
        source_kind="field",
        source_config={"field_name": "title"},
        target_key="dc:title",
        settings={},
        sort_order=1,
        is_enabled=True,
    )
    pub_set.rules = [r_pub]

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [pub_set]
    mock_db.execute.return_value = mock_res

    index = await metadata_mapping_service.get_mapping_index(mock_db, "oai_dc")
    assert "object" in index
    cms = index["object"]
    assert len(cms.rules) == 1
    assert cms.rules[0].target_key == "dc:title"


@pytest.mark.asyncio
async def test_new_lido_object_mapping_defaults_title_to_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_db = AsyncMock()
    added: list[object] = []
    mock_db.add = MagicMock(side_effect=added.append)
    portal_result = MagicMock()
    portal_result.scalar_one_or_none.return_value = PortalConfig(
        key="default",
        site_title={"de": "Sammlung Beispiel"},
    )
    mock_db.execute.return_value = portal_result

    async def get_created_set(_: AsyncMock, __: uuid.UUID) -> ExportMappingSet:
        return next(item for item in added if isinstance(item, ExportMappingSet))

    monkeypatch.setattr(metadata_mapping_service, "get_mapping_set", get_created_set)

    await metadata_mapping_service.create_mapping_set(
        mock_db,
        ExportMappingSetCreate(
            format_key="lido",
            profile_id="lido_core",
            profile_version="1.0",
            record_type="object",
            name="LIDO Objects",
        ),
    )

    created = next(item for item in added if isinstance(item, ExportMappingSet))
    rules = [item for item in added if isinstance(item, ExportMappingRule)]
    assert created.institution_config == {"institution_name": "Sammlung Beispiel"}
    assert len(rules) == 1
    assert rules[0].source_kind == SourceKind.FIELD.value
    assert rules[0].source_config == {"field_name": "label"}
    assert rules[0].target_key == (
        "lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue"
    )

@pytest.mark.asyncio
async def test_lido_subtype_authority_validation_lists_missing_subtypes() -> None:
    mapping_set = ExportMappingSet(
        id=uuid.uuid4(),
        format_key="lido",
        profile_id="lido_core",
        record_type="object",
        name="LIDO Objects",
    )
    compiled = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.RECORD,
                source_config={"property": "target_subtype"},
                target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
            )
        ],
    )
    missing = RecordSubtype(primary_type="object", name="archivalie", label={"de": "Archivalie / Druckwerk"})
    linked = RecordSubtype(
        primary_type="object",
        name="druckgrafik",
        label={"de": "Druckgrafik"},
        concept_uri="https://vocab.getty.edu/aat/300041347",
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [missing, linked]
    mock_db.execute.return_value = mock_result

    diagnostics = await metadata_mapping_service._validate_lido_subtype_authorities(
        mock_db, mapping_set, compiled
    )

    assert [diagnostic.code for diagnostic in diagnostics] == ["subtype_authority_missing"]
    assert diagnostics[0].message == "Subtypen ohne Normdaten: Archivalie / Druckwerk."


@pytest.mark.asyncio
async def test_optimistic_locking_exception_on_version_mismatch() -> None:
    mock_db = AsyncMock()

    mock_set = ExportMappingSet(
        id=uuid.uuid4(),
        format_key="oai_dc",
        profile_id="oai_dc_simple",
        record_type="object",
        name="Draft Set",
        status="draft",
        version=5,
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_set
    mock_db.execute.return_value = mock_res

    update_data = ExportMappingSetUpdate(name="Updated Name")

    with pytest.raises(OptimisticLockError) as exc_info:
        await metadata_mapping_service.update_mapping_set(
            mock_db,
            mock_set.id,
            update_data,
            expected_version=4,  # Mismatch! (current is 5)
        )
    assert "Konflikt" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cannot_edit_rules_on_published_set() -> None:
    mock_db = AsyncMock()

    pub_set = ExportMappingSet(
        id=uuid.uuid4(),
        format_key="oai_dc",
        profile_id="oai_dc_simple",
        record_type="object",
        name="Published Set",
        status="published",
        version=1,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = pub_set
    mock_db.execute.return_value = mock_res

    with pytest.raises(ValueError) as exc:
        await metadata_mapping_service.create_rule(
            mock_db,
            pub_set.id,
            ExportMappingRuleCreate(target_key="dc:title"),
        )
    assert "status='draft'" in str(exc.value)


# ---------------------------------------------------------------------------
# API Endpoints Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_mapping_sets_api_crud_flow() -> None:
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@example.org",
        hashed_password="hash",
        role="admin",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user

    set_id = uuid.uuid4()
    rule_id = uuid.uuid4()

    mock_set = ExportMappingSet(
        id=set_id,
        format_key="oai_dc",
        profile_id="oai_dc_simple",
        profile_version="2.0",
        record_type="object",
        target_subtype=None,
        name="OAI-DC Object",
        status="draft",
        revision=1,
        based_on_id=None,
        institution_config={},
        version=1,
        created_by=admin_user.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        published_at=None,
        rules=[],
    )

    # Mock service functions
    orig_list = metadata_mapping_service.list_mapping_sets
    orig_get = metadata_mapping_service.get_mapping_set
    orig_create = metadata_mapping_service.create_mapping_set
    orig_update = metadata_mapping_service.update_mapping_set
    orig_delete = metadata_mapping_service.delete_mapping_set
    orig_create_rule = metadata_mapping_service.create_rule
    orig_delete_rule = metadata_mapping_service.delete_rule
    orig_validate = metadata_mapping_service.validate_mapping_set
    orig_publish = metadata_mapping_service.publish_mapping_set

    try:
        metadata_mapping_service.list_mapping_sets = AsyncMock(return_value=[mock_set])
        metadata_mapping_service.get_mapping_set = AsyncMock(return_value=mock_set)
        metadata_mapping_service.create_mapping_set = AsyncMock(return_value=mock_set)
        metadata_mapping_service.update_mapping_set = AsyncMock(return_value=mock_set)
        metadata_mapping_service.delete_mapping_set = AsyncMock(return_value=None)

        mock_rule = ExportMappingRule(
            id=rule_id,
            rule_key=uuid.uuid4(),
            mapping_set_id=set_id,
            source_kind="field",
            source_config={"field_name": "title"},
            target_key="dc:title",
            settings={},
            sort_order=1,
            is_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        metadata_mapping_service.create_rule = AsyncMock(return_value=mock_rule)
        metadata_mapping_service.delete_rule = AsyncMock(return_value=None)
        metadata_mapping_service.validate_mapping_set = AsyncMock(return_value=[])

        pub_set = ExportMappingSet(
            id=set_id,
            format_key="oai_dc",
            profile_id="oai_dc_simple",
            profile_version="2.0",
            record_type="object",
            target_subtype=None,
            name="OAI-DC Object",
            status="published",
            revision=1,
            based_on_id=None,
            institution_config={},
            version=2,
            created_by=admin_user.id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            published_at=datetime.now(UTC),
            rules=[mock_rule],
        )
        metadata_mapping_service.publish_mapping_set = AsyncMock(return_value=pub_set)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. GET /v1/export-mapping-sets
            res = await client.get("/v1/export-mapping-sets?record_type=object")
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 1
            assert data[0]["id"] == str(set_id)

            # 2. GET /v1/export-mapping-sets/{id}
            res = await client.get(f"/v1/export-mapping-sets/{set_id}")
            assert res.status_code == 200
            assert res.json()["name"] == "OAI-DC Object"

            # 3. POST /v1/export-mapping-sets
            payload = {
                "format_key": "oai_dc",
                "profile_id": "oai_dc_simple",
                "record_type": "object",
                "name": "OAI-DC Object",
            }
            res = await client.post("/v1/export-mapping-sets", json=payload)
            assert res.status_code == 201

            # 4. PATCH /v1/export-mapping-sets/{id} with If-Match
            res = await client.patch(
                f"/v1/export-mapping-sets/{set_id}",
                json={"name": "Renamed OAI-DC"},
                headers={"If-Match": "1"},
            )
            assert res.status_code == 200

            # 5. POST /v1/export-mapping-sets/{id}/rules
            rule_payload = {
                "source_kind": "field",
                "source_config": {"field_name": "title"},
                "target_key": "dc:title",
                "sort_order": 1,
            }
            res = await client.post(f"/v1/export-mapping-sets/{set_id}/rules", json=rule_payload)
            assert res.status_code == 201
            assert res.json()["target_key"] == "dc:title"

            # 6. POST /v1/export-mapping-sets/{id}/validate
            res = await client.post(f"/v1/export-mapping-sets/{set_id}/validate")
            assert res.status_code == 200
            assert res.json() == []

            # 7. POST /v1/export-mapping-sets/{id}/publish
            res = await client.post(
                f"/v1/export-mapping-sets/{set_id}/publish",
                headers={"If-Match": "1"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "published"

            # 8. DELETE rule and DELETE set
            res = await client.delete(f"/v1/export-mapping-sets/{set_id}/rules/{rule_id}")
            assert res.status_code == 204

            res = await client.delete(f"/v1/export-mapping-sets/{set_id}")
            assert res.status_code == 204

    finally:
        metadata_mapping_service.list_mapping_sets = orig_list
        metadata_mapping_service.get_mapping_set = orig_get
        metadata_mapping_service.create_mapping_set = orig_create
        metadata_mapping_service.update_mapping_set = orig_update
        metadata_mapping_service.delete_mapping_set = orig_delete
        metadata_mapping_service.create_rule = orig_create_rule
        metadata_mapping_service.delete_rule = orig_delete_rule
        metadata_mapping_service.validate_mapping_set = orig_validate
        metadata_mapping_service.publish_mapping_set = orig_publish
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_preview_endpoint_renders_xml_and_diagnostics() -> None:
    admin_user = User(
        id=uuid.uuid4(),
        email="admin2@example.org",
        hashed_password="hash",
        role="admin",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    set_id = uuid.uuid4()
    record_id = uuid.uuid4()

    orig_preview = metadata_mapping_service.preview_mapping_set
    try:
        metadata_mapping_service.preview_mapping_set = AsyncMock(
            return_value=("<lido:lidoWrap/>", [])
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                f"/v1/export-mapping-sets/{set_id}/preview",
                json={"record_id": str(record_id)},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["xml"] == "<lido:lidoWrap/>"
            assert data["diagnostics"] == []
        call_args = metadata_mapping_service.preview_mapping_set.await_args.args
        assert call_args[1] == set_id
        assert call_args[2] == record_id
    finally:
        metadata_mapping_service.preview_mapping_set = orig_preview
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_preview_endpoint_rejects_unknown_set() -> None:
    admin_user = User(
        id=uuid.uuid4(),
        email="admin3@example.org",
        hashed_password="hash",
        role="admin",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    set_id = uuid.uuid4()
    record_id = uuid.uuid4()

    orig_preview = metadata_mapping_service.preview_mapping_set
    try:
        metadata_mapping_service.preview_mapping_set = AsyncMock(
            side_effect=ValueError("ExportMappingSet nicht gefunden.")
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                f"/v1/export-mapping-sets/{set_id}/preview",
                json={"record_id": str(record_id)},
            )
            assert res.status_code == 400
    finally:
        metadata_mapping_service.preview_mapping_set = orig_preview
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_export_mapping_set_to_yaml() -> None:
    set_id = uuid.uuid4()
    mock_set = ExportMappingSet(
        id=set_id,
        format_key="lido",
        profile_id="lido-v1.1",
        profile_version="1.1",
        record_type="object",
        name="LIDO Object Test",
        revision=2,
        institution_config={"institution_name": "Test Museum"},
    )
    rule = ExportMappingRule(
        id=uuid.uuid4(),
        rule_key=uuid.uuid4(),
        mapping_set_id=set_id,
        source_kind="field",
        source_config={"field_name": "title"},
        target_key="lido:appellationValue",
        settings={},
        sort_order=0,
        is_enabled=True,
    )
    mock_set.rules = [rule]

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_set
    mock_db.execute.return_value = mock_result

    yaml_str, filename = await metadata_mapping_service.export_mapping_set_to_yaml(mock_db, set_id)
    assert "format_key: lido" in yaml_str
    assert "record_type: object" in yaml_str
    assert "target_key: lido:appellationValue" in yaml_str
    assert "field_name: title" in yaml_str
    assert filename == "export-mapping-lido-object-rev2.yaml"


@pytest.mark.asyncio
async def test_import_mapping_set_from_yaml_creates_draft() -> None:
    yaml_content = """
format_key: lido
profile_id: lido-v1.1
profile_version: "1.1"
record_type: object
name: Imported LIDO Mapping
institution_config:
  institution_name: Sample Archive
rules:
  - source_kind: field
    field_name: title
    target_key: lido:appellationValue
    sort_order: 0
    is_enabled: true
"""
    mock_db = AsyncMock()
    mock_rev_res = MagicMock()
    mock_rev_res.scalars.return_value.all.return_value = []
    mock_pub_res = MagicMock()
    mock_pub_res.scalar_one_or_none.return_value = None
    title_field = MagicMock()
    title_field.id = uuid.uuid4()
    title_field.name = "title"
    title_field.field_type = "text"
    mock_fields_res = MagicMock()
    mock_fields_res.scalars.return_value.all.return_value = [title_field]
    mock_refresh_res = MagicMock()
    mock_refresh_res.scalar_one_or_none.side_effect = lambda: next(
        (x for x in added if isinstance(x, ExportMappingSet)), None
    )

    mock_db.execute.side_effect = [mock_rev_res, mock_pub_res, mock_fields_res, mock_refresh_res]

    added: list[object] = []
    mock_db.add = MagicMock(side_effect=lambda obj: added.append(obj))

    imported_set, warnings, rules_count = await metadata_mapping_service.import_mapping_set_from_yaml(
        mock_db,
        yaml_content,
        dry_run=False,
    )
    assert warnings == []
    assert rules_count == 1
    created_set = next(x for x in added if isinstance(x, ExportMappingSet))
    created_rule = next(x for x in added if isinstance(x, ExportMappingRule))
    assert created_set.format_key == "lido"
    assert created_set.record_type == "object"
    assert created_set.status == "draft"
    assert created_set.revision == 1
    assert created_rule.field_definition_id == title_field.id
    assert created_rule.target_key == "lido:appellationValue"


@pytest.mark.asyncio
async def test_yaml_export_and_import_endpoints() -> None:
    admin_user = User(
        id=uuid.uuid4(),
        email="admin_yaml@example.org",
        hashed_password="hash",
        role="admin",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    set_id = uuid.uuid4()

    orig_export = metadata_mapping_service.export_mapping_set_to_yaml
    orig_import = metadata_mapping_service.import_mapping_set_from_yaml

    dummy_set = ExportMappingSet(
        id=set_id,
        format_key="lido",
        record_type="object",
        name="LIDO",
        status="draft",
        revision=1,
    )
    dummy_set.rules = []

    try:
        metadata_mapping_service.export_mapping_set_to_yaml = AsyncMock(
            return_value=("format_key: lido\nrecord_type: object\n", "export-mapping-lido-object-rev1.yaml")
        )
        metadata_mapping_service.import_mapping_set_from_yaml = AsyncMock(
            return_value=(dummy_set, ["Notice: test warning"], 0)
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Export YAML
            res_export = await client.get(f"/v1/export-mapping-sets/{set_id}/yaml")
            assert res_export.status_code == 200
            assert "format_key: lido" in res_export.text
            assert "export-mapping-lido-object-rev1.yaml" in res_export.headers.get("Content-Disposition", "")

            # 2. Import YAML
            files = {"file": ("mapping.yaml", b"format_key: lido\nrecord_type: object\n", "application/x-yaml")}
            res_import = await client.post("/v1/export-mapping-sets/import-yaml", files=files)
            assert res_import.status_code == 200
            data = res_import.json()
            assert data["format_key"] == "lido"
            assert data["warnings"] == ["Notice: test warning"]
    finally:
        metadata_mapping_service.export_mapping_set_to_yaml = orig_export
        metadata_mapping_service.import_mapping_set_from_yaml = orig_import
        app.dependency_overrides.pop(get_current_user, None)

