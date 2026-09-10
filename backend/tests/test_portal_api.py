# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.api.v1 import portal_public
from katalon.api.v1.portal import PortalConfigRead
from katalon.core.dependencies import try_get_current_user
from katalon.core.models import (
    Entity,
    FieldDefinition,
    Object,
    Occurrence,
    Place,
    PortalConfig,
    Relation,
    User,
    VocabularyTerm,
)
from katalon.database import get_db
from katalon.main import app


def _result(*, total: int | None = None, items: list[object] | None = None) -> MagicMock:
    result = MagicMock()
    if total is not None:
        result.scalar_one.return_value = total
    result.scalars.return_value.all.return_value = items or []
    return result


@pytest.mark.asyncio
async def test_v1_reads_require_a_token() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/objects")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_portal_lists_only_public_objects() -> None:
    statements: list[str] = []
    public_object = Object(
        id=uuid.uuid4(),
        idno="OBJ-1",
        status="public",
        collection_status="active",
        metadata_={},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        version=1,
    )
    public_field = FieldDefinition(
        id=uuid.uuid4(),
        target_type="object",
        name="label",
        label={"de": "Titel"},
        field_type="text",
        is_public=True,
    )
    session = AsyncMock()

    async def execute(statement):
        statements.append(str(statement))
        if len(statements) == 1:
            return _result(total=1)
        if len(statements) == 2:
            return _result(items=[public_object])
        return _result(items=[public_field])

    session.execute.side_effect = execute

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/objects")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [str(public_object.id)]
    assert "objects.status IN" in statements[0]
    item = response.json()["items"][0]
    assert "version" not in item
    assert "search_vector" not in item


@pytest.mark.asyncio
async def test_portal_record_omits_internal_metadata() -> None:
    record = Object(
        id=uuid.uuid4(),
        idno="OBJ-1",
        status="public",
        collection_status="active",
        metadata_={"label": "Public", "internal_note": "Do not publish"},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        deleted_at=None,
        version=1,
    )
    fields = [
        FieldDefinition(
            id=uuid.uuid4(),
            target_type="object",
            name="label",
            label={},
            field_type="text",
            is_public=True,
        ),
        FieldDefinition(
            id=uuid.uuid4(),
            target_type="object",
            name="internal_note",
            label={},
            field_type="text",
            is_public=False,
        ),
    ]
    session = AsyncMock()
    record_result = MagicMock()
    record_result.scalar_one_or_none.return_value = record
    session.execute.side_effect = [record_result, _result(items=[fields[0]])]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{record.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["metadata_"] == {"label": "Public"}


@pytest.mark.asyncio
async def test_portal_staff_login_uses_internal_record_projection(monkeypatch) -> None:
    record = Object(
        id=uuid.uuid4(),
        idno="OBJ-1",
        status="draft",
        collection_status="active",
        metadata_={"internal_note": "Nur intern"},
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    staff_user = User(email="staff@example.test", hashed_password="unused", role="editor")
    get_object = AsyncMock(return_value=record)
    monkeypatch.setattr(portal_public.objects, "get_object", get_object)

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[try_get_current_user] = lambda: staff_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{record.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)

    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert response.json()["metadata_"] == {"internal_note": "Nur intern"}
    assert get_object.await_args.args[2] is staff_user


@pytest.mark.parametrize(
    ("path", "record"),
    [
        ("objects", Object(idno="OBJ-1", collection_status="active")),
        ("entities", Entity(idno="ENT-1", entity_type="person")),
        ("places", Place(idno="PLC-1", place_type="city")),
        ("occurrences", Occurrence(idno="OCC-1", occurrence_type="event")),
    ],
)
@pytest.mark.asyncio
async def test_portal_record_responses_exclude_internal_orm_fields(
    path: str, record: object
) -> None:
    record.id = uuid.uuid4()
    record.status = "public"
    record.metadata_ = {}
    record.search_vector = "internal search data"
    record.created_at = datetime.now()
    record.updated_at = datetime.now()
    record.version = 99
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = record
    session.execute.return_value = result

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/{path}/{record.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert "version" not in body
    assert "search_vector" not in body


@pytest.mark.asyncio
async def test_portal_never_returns_procedures_or_their_relations() -> None:
    session = AsyncMock()
    statements: list[str] = []

    async def execute(statement):
        statements.append(str(statement))
        return _result(items=[])

    session.execute.side_effect = execute

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            procedures = await client.get("/portal/v1/procedures")
            relations = await client.get("/portal/v1/relations")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert procedures.status_code == 404
    assert relations.status_code == 200
    assert relations.json() == []
    assert "relations.from_type = :from_type_1" in statements[0]
    assert "relations.to_type = :to_type_1" in statements[0]


@pytest.mark.asyncio
async def test_portal_relations_use_public_endpoints_before_limit() -> None:
    relation = Relation(
        id=uuid.uuid4(),
        from_type="object",
        from_id=uuid.uuid4(),
        to_type="entity",
        to_id=uuid.uuid4(),
        relation_type="depicts",
        metadata_={"internal": "never public"},
    )
    session = AsyncMock()
    statements: list[str] = []

    async def execute(statement):
        statements.append(str(statement))
        return _result(items=[relation])

    session.execute.side_effect = execute

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/relations?limit=1")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert "metadata_" not in response.json()[0]
    assert "EXISTS" in statements[0]
    assert statements[0].index("EXISTS") < statements[0].index("LIMIT")


@pytest.mark.asyncio
async def test_portal_schema_is_narrow_and_excludes_deleted_fields() -> None:
    field = FieldDefinition(
        id=uuid.uuid4(),
        target_type="object",
        name="material",
        label={"de": "Material"},
        field_type="text",
        settings={"hint": "visible"},
        show_in_detail=True,
        detail_slot="sidebar",
        detail_role="none",
        is_deleted=False,
        is_required=True,
        is_repeatable=True,
        is_searchable=True,
        is_facet=False,
        sort_order=1,
    )
    session = AsyncMock()
    session.execute.return_value = _result(items=[field])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/schema/object")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "material",
            "label": {"de": "Material"},
            "field_type": "text",
            "is_repeatable": True,
            "is_searchable": True,
            "is_facet": False,
            "parent_id": None,
            "settings": {"hint": "visible"},
            "show_in_detail": True,
            "detail_slot": "sidebar",
            "detail_role": "none",
        }
    ]


@pytest.mark.asyncio
async def test_portal_exposes_terms_only_through_public_searchable_vocab_field() -> None:
    vocabulary_id = uuid.uuid4()
    field_result = MagicMock()
    field_result.scalar_one_or_none.return_value = MagicMock(
        settings={"vocabulary_id": str(vocabulary_id)}
    )
    term = VocabularyTerm(
        id=uuid.uuid4(),
        vocabulary_id=vocabulary_id,
        term="stone",
        label={"de": "Stein"},
        inverse_label={},
        metadata_={},
        parent_id=None,
        applies_from=[],
        applies_to=[],
    )
    session = AsyncMock()
    session.execute.side_effect = [field_result, _result(items=[term])]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/schema/object/fields/material/terms")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(term.id),
            "term": "stone",
            "label": {"de": "Stein"},
            "parent_id": None,
        }
    ]


@pytest.mark.asyncio
async def test_portal_config_rewrites_uploaded_logo_url(monkeypatch) -> None:
    config = PortalConfigRead(
        site_title="Katalon",
        site_subtitle="",
        hero_text="",
        featured_object_ids=[],
        facet_fields={},
        accent_color="#1e3a8a",
        logo_url="/v1/portal/logo/file",
        placeholder_image_url="",
        color_tokens={},
        browse_enabled_types=["object", "entity", "place", "occurrence"],
    )
    monkeypatch.setattr(
        "katalon.api.v1.portal_public.portal.get_portal_config", AsyncMock(return_value=config)
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/portal/v1/portal/config")

    assert response.status_code == 200
    assert response.json()["logo_url"] == "/portal/v1/portal/logo/file"
    assert response.json()["browse_enabled_types"] == ["object", "entity", "place", "occurrence"]


@pytest.mark.parametrize(
    ("saved_facets", "expected_system_facets"),
    [
        ({}, ["record_type", "status"]),
        ({"_system": ["status"]}, ["status"]),
        ({"_system": []}, []),
    ],
)
@pytest.mark.asyncio
async def test_portal_config_preserves_system_facet_visibility(
    saved_facets: dict[str, list[str]], expected_system_facets: list[str]
) -> None:
    config_result = MagicMock()
    config_result.scalar_one_or_none.return_value = PortalConfig(facet_fields=saved_facets)
    facet_result = MagicMock()
    facet_result.all.return_value = []
    admin_result = MagicMock()
    admin_result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute.side_effect = [config_result, facet_result, admin_result]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/portal/config")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["facet_fields"]["_system"] == expected_system_facets


@pytest.mark.asyncio
async def test_portal_config_returns_facet_display_settings() -> None:
    config_result = MagicMock()
    config_result.scalar_one_or_none.return_value = PortalConfig(
        facet_sort="alpha", facet_initial_count=25
    )
    facet_result = MagicMock()
    facet_result.all.return_value = []
    admin_result = MagicMock()
    admin_result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute.side_effect = [config_result, facet_result, admin_result]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/portal/config")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["facet_sort"] == "alpha"
    assert body["facet_initial_count"] == 25


@pytest.mark.asyncio
async def test_portal_config_update_returns_resolved_facets() -> None:
    from katalon.core.dependencies import get_current_user

    admin_user = User(
        id=uuid.uuid4(),
        email="admin@example.org",
        hashed_password="x",
        role="admin",
        is_active=True,
    )
    portal_cfg = PortalConfig(
        key="default",
        facet_fields={"_system": ["record_type"], "object": ["inherited_entity_name"]},
    )

    config_result1 = MagicMock()
    config_result1.scalar_one_or_none.return_value = portal_cfg
    config_result2 = MagicMock()
    config_result2.scalar_one_or_none.return_value = portal_cfg
    from types import SimpleNamespace

    facet_row = SimpleNamespace(target_type="object", name="material")
    facet_result = MagicMock()
    facet_result.all.return_value = [facet_row]

    admin_result = MagicMock()
    admin_result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute.side_effect = [config_result1, config_result2, facet_result, admin_result]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/v1/portal/config",
                json={
                    "facet_fields": {
                        "_system": ["record_type"],
                        "object": ["inherited_entity_name"],
                    },
                    "facet_sort": "alpha",
                    "facet_initial_count": 15,
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["facet_sort"] == "alpha"
    assert body["facet_initial_count"] == 15
    assert "material" in body["facet_fields"]["object"]
    assert "inherited_entity_name" in body["facet_fields"]["object"]
    assert body["facet_fields"]["_system"] == ["record_type"]


@pytest.mark.asyncio
async def test_portal_config_saves_and_returns_terminology_overrides() -> None:
    from katalon.core.dependencies import get_current_user

    admin_user = User(
        id=uuid.uuid4(),
        email="admin@example.org",
        hashed_password="x",
        role="admin",
        is_active=True,
    )
    portal_cfg = PortalConfig(key="default")

    config_result1 = MagicMock()
    config_result1.scalar_one_or_none.return_value = portal_cfg
    config_result2 = MagicMock()
    config_result2.scalar_one_or_none.return_value = portal_cfg
    facet_result = MagicMock()
    facet_result.all.return_value = []
    admin_result = MagicMock()
    admin_result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute.side_effect = [config_result1, config_result2, facet_result, admin_result]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/v1/portal/config",
                json={
                    "terminology": {
                        "object": {
                            "singular": {"de": "Werk", "en": "Work"},
                            "plural": {"de": "Werke", "en": "Works"},
                        }
                    }
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    terminology = response.json()["terminology"]
    assert terminology["object"]["singular"] == {"de": "Werk", "en": "Work"}
    assert terminology["object"]["plural"] == {"de": "Werke", "en": "Works"}
    assert portal_cfg.terminology["object"]["plural"]["de"] == "Werke"


@pytest.mark.asyncio
async def test_portal_config_rejects_unknown_terminology_record_type() -> None:
    from katalon.core.dependencies import get_current_user

    admin_user = User(
        id=uuid.uuid4(), email="admin@example.org", hashed_password="x", role="admin", is_active=True,
    )

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/v1/portal/config",
                json={"terminology": {"storage_location": {"singular": {"de": "Standort"}}}},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_portal_config_saves_and_returns_homepage_blocks() -> None:
    from katalon.core.dependencies import get_current_user

    admin_user = User(
        id=uuid.uuid4(),
        email="admin@example.org",
        hashed_password="x",
        role="admin",
        is_active=True,
    )
    portal_cfg = PortalConfig(key="default")

    config_result1 = MagicMock()
    config_result1.scalar_one_or_none.return_value = portal_cfg
    config_result2 = MagicMock()
    config_result2.scalar_one_or_none.return_value = portal_cfg
    facet_result = MagicMock()
    facet_result.all.return_value = []
    admin_result = MagicMock()
    admin_result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute.side_effect = [config_result1, config_result2, facet_result, admin_result]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/v1/portal/config",
                json={
                    "homepage_blocks": [
                        {"id": "b1", "type": "curated", "enabled": True, "title": {"de": "Highlights"}},
                        {"id": "b2", "type": "collections", "enabled": True, "title": {}, "collections_mode": "top", "limit": 6},
                    ]
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    blocks = response.json()["homepage_blocks"]
    assert [b["id"] for b in blocks] == ["b1", "b2"]
    assert blocks[0]["title"] == {"de": "Highlights"}
    assert blocks[1]["collections_mode"] == "top"
    assert portal_cfg.homepage_blocks[1]["limit"] == 6


@pytest.mark.asyncio
async def test_portal_config_rejects_unknown_homepage_block_type() -> None:
    from katalon.core.dependencies import get_current_user

    admin_user = User(
        id=uuid.uuid4(), email="admin@example.org", hashed_password="x", role="admin", is_active=True,
    )

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                "/v1/portal/config",
                json={"homepage_blocks": [{"id": "b1", "type": "carousel", "enabled": True, "title": {}}]},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_portal_has_no_feedback_write_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/portal/v1/feedback", json={})
        authenticated_api = await client.post("/v1/feedback", json={})

    assert response.status_code == 404
    assert authenticated_api.status_code == 401


@pytest.mark.asyncio
async def test_portal_search_rejects_procedures(monkeypatch) -> None:
    search = AsyncMock()
    monkeypatch.setattr("katalon.api.v1.portal_public.search_service.search", search)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/portal/v1/search?type=procedure")

    assert response.status_code == 422
    search.assert_not_awaited()


@pytest.mark.asyncio
async def test_portal_advanced_search_uses_validated_filter(monkeypatch) -> None:
    advanced_filter = {"bool": {"filter": [{"match_all": {}}]}}
    resolve = AsyncMock(return_value=advanced_filter)
    search = AsyncMock(
        return_value={
            "total": 0,
            "page": 1,
            "page_size": 20,
            "items": [],
            "facets": {},
        }
    )
    monkeypatch.setattr(portal_public, "resolve_query", resolve)
    monkeypatch.setattr(portal_public.search_service, "search", search)
    config_result = MagicMock()
    config_result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute.return_value = config_result

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/portal/v1/search/advanced",
                json={
                    "query": {
                        "version": 1,
                        "record_type": "object",
                        "group": {
                            "mode": "all",
                            "clauses": [
                                {
                                    "kind": "field",
                                    "field": "title",
                                    "operator": "contains",
                                    "value": "Bremen",
                                }
                            ],
                        },
                    },
                    "q": "Ansicht",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert search.await_args.kwargs["advanced_filter"] == advanced_filter
    assert search.await_args.kwargs["record_type"] == "object"
    assert search.await_args.kwargs["status"] == "public"


@pytest.mark.asyncio
async def test_portal_search_limits_elasticsearch_to_public_record_types(monkeypatch) -> None:
    captured: dict = {}
    config = MagicMock(subtitle_fields={"object": ["creator"]})
    config_result = MagicMock()
    config_result.scalar_one_or_none.return_value = config
    session = AsyncMock()
    session.execute.return_value = config_result

    async def search(**kwargs):
        captured.update(kwargs)
        return {"total": 0, "page": 1, "page_size": 20, "items": [], "facets": {}}

    async def override_db():
        yield session

    monkeypatch.setattr("katalon.api.v1.portal_public.search_service.search", search)
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/portal/v1/search?meta_event_date=Paläolithikum&meta_event_date=Neolithikum"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert captured["record_type"] is None
    assert captured["record_types"] == ("object", "entity", "place", "occurrence", "collection")
    assert captured["status"] == "public"
    assert captured["extra_filters"] == {"event_date": ["Paläolithikum", "Neolithikum"]}
    assert captured["subtitle_fields"] == {"object": ["creator"]}


@pytest.mark.asyncio
async def test_portal_search_forwards_numeric_range_filters(monkeypatch) -> None:
    captured: dict = {}
    config_result = MagicMock()
    config_result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute.return_value = config_result

    async def search(**kwargs):
        captured.update(kwargs)
        return {"total": 0, "page": 1, "page_size": 20, "items": [], "facets": {}}

    async def override_db():
        yield session

    monkeypatch.setattr("katalon.api.v1.portal_public.search_service.search", search)
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/search?range_year_from=1900&range_year_to=1950")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert captured["numeric_filters"] == {"year": (1900.0, 1950.0)}


@pytest.mark.asyncio
async def test_portal_search_forwards_rel_collection(monkeypatch) -> None:
    captured: dict = {}
    config_result = MagicMock()
    config_result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute.return_value = config_result

    async def search(**kwargs):
        captured.update(kwargs)
        return {"total": 0, "page": 1, "page_size": 20, "items": [], "facets": {}}

    async def override_db():
        yield session

    monkeypatch.setattr("katalon.api.v1.portal_public.search_service.search", search)
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/search?rel_collection=Nachlass+Müller")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert captured["rel_filters"] == {"related_collections": ["Nachlass Müller"]}


@pytest.mark.asyncio
async def test_portal_config_endpoints_are_browser_cacheable() -> None:
    """The portal refetches these on every page view; they must be cacheable.

    Under crawler traffic these multiply per crawled page, so a short TTL keeps
    them out of the request chain entirely.
    """
    session = AsyncMock()
    session.execute.return_value = _result(items=[])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in (
                "/portal/v1/pages",
                "/portal/v1/banners/active/portal",
                "/portal/v1/theme",
            ):
                response = await client.get(path)
                assert response.status_code == 200, path
                assert response.headers["cache-control"] == "public, max-age=60", path
    finally:
        app.dependency_overrides.pop(get_db, None)



@pytest.mark.asyncio
async def test_portal_config_is_browser_cacheable() -> None:
    result = MagicMock()
    # First lookup is the PortalConfig row; later lookups (AdminConfig for
    # supported languages) fall back to defaults.
    result.scalar_one_or_none.side_effect = [PortalConfig(key="default"), None]
    result.all.return_value = []
    session = AsyncMock()
    session.execute.return_value = result

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/portal/config")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=60"

@pytest.mark.asyncio
async def test_portal_schema_cache_header_depends_on_the_viewer() -> None:
    """The staff projection contains non-public fields and must not be shared."""
    session = AsyncMock()
    session.execute.return_value = _result(items=[])

    async def override_db():
        yield session

    staff_user = User(id=uuid.uuid4(), email="s@example.org", role="editor", is_active=True)

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            anon = await client.get("/portal/v1/schema/object")
            assert anon.headers["cache-control"] == "public, max-age=60"
            assert anon.headers["vary"] == "Authorization"

            app.dependency_overrides[try_get_current_user] = lambda: staff_user
            staff = await client.get("/portal/v1/schema/object")
            assert staff.headers["cache-control"] == "private, no-store"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_filter_facet_names_whitelists_only_is_facet_fields() -> None:
    """Anonymous callers may aggregate only fields explicitly marked is_facet
    (docs carry facet_all_* for every public field, so without this gate any
    public field would become aggregatable)."""
    db = AsyncMock()
    rows = MagicMock()
    rows.all.return_value = [("material",), ("year",)]
    db.execute.return_value = rows

    result = await portal_public._filter_facet_names(
        db,
        ["material", "year", "not_a_facet", "inherited_entity_ort", "related_entities"],
        ("object",),
    )

    assert result == ["inherited_entity_ort", "material", "related_entities", "year"]


@pytest.mark.asyncio
async def test_filter_facet_names_allows_facet_across_any_searched_type() -> None:
    db = AsyncMock()
    rows = MagicMock()
    rows.all.return_value = [("ort",)]
    db.execute.return_value = rows

    result = await portal_public._filter_facet_names(db, ["ort"], ("object", "entity", "place"))

    assert result == ["ort"]
