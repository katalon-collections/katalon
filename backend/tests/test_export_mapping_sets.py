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
    User,
)
from katalon.core.schemas import (
    ExportMappingRuleCreate,
    ExportMappingSetUpdate,
)
from katalon.integrations.metadata_format import SourceKind
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
