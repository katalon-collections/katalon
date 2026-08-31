import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.core.dependencies import get_current_user
from katalon.core.models import Object, User
from katalon.database import get_db
from katalon.main import app


def _count_result(total: int = 0) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = total
    return result


def _items_result(items: list | None = None) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items or []
    return result


def _one_result(value) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        ("viewer", 403),
        ("cataloger", 200),
        ("editor", 200),
        ("admin", 200),
        ("superuser", 200),
    ],
)
@pytest.mark.parametrize(
    "path",
    [
        "/v1/record-subtypes",
        "/v1/idno/next?type=invalid",
    ],
)
@pytest.mark.asyncio
async def test_form_lookup_routes_require_manage_content(
    path: str,
    role: str,
    expected_status: int,
) -> None:
    user = User(id=uuid.uuid4(), email=f"{role}@example.org", hashed_password="x", role=role)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_items_result())

    async def override_db():
        yield session

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(path)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("path", "status_column"),
    [
        ("/portal/v1/objects", "objects.status"),
    ],
)
@pytest.mark.asyncio
async def test_anonymous_lists_keep_public_visibility_with_explicit_status(
    path: str,
    status_column: str,
) -> None:
    statements: list[str] = []
    session = AsyncMock()

    async def execute(statement):
        statements.append(str(statement))
        return _count_result() if len(statements) == 1 else _items_result()

    session.execute = AsyncMock(side_effect=execute)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(path, params={"status": "draft"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert status_column in statements[0]
    assert f"{status_column} IN (__[POSTCOMPILE_status_" in statements[0]




@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("post", "/v1/objects", {"idno": "OBJ-1", "metadata": {}}),
        ("post", "/v1/entities", {"idno": "ENT-1", "entity_type": "person", "metadata": {}}),
        ("post", "/v1/places", {"idno": "PLC-1", "metadata": {}}),
        (
            "post",
            "/v1/occurrences",
            {"idno": "OCC-1", "occurrence_type": "event", "metadata": {}},
        ),
        (
            "post",
            "/v1/procedures",
            {"idno": "PRO-1", "procedure_type": "loan_out", "metadata": {}},
        ),
        ("post", "/v1/relations", {
            "from_type": "object",
            "from_id": str(uuid.uuid4()),
            "to_type": "entity",
            "to_id": str(uuid.uuid4()),
            "relation_type": "mentions",
            "metadata": {},
        }),
        ("post", "/v1/pages", {"slug": "test", "title": {}, "content": {}}),
        ("post", "/v1/banners", {"message": "Test"}),
    ],
)
@pytest.mark.asyncio
async def test_viewer_cannot_use_mutating_admin_or_content_routes(
    method: str,
    path: str,
    json_body: dict,
) -> None:
    viewer = User(id=uuid.uuid4(), email="viewer@example.org", hashed_password="x", role="viewer")
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_one_result(None))

    async def override_db():
        yield session

    app.dependency_overrides[get_current_user] = lambda: viewer
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await getattr(client, method)(path, json=json_body)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_anonymous_media_list_hides_draft_object() -> None:
    obj = Object(id=uuid.uuid4(), idno="OBJ-1", status="draft", metadata_={})
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_one_result(obj))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{obj.id}/media")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
