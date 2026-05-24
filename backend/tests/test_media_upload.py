"""Tests for media upload API endpoints."""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.core.dependencies import get_current_user
from katalon.core.models import MediaFile, Object, User
from katalon.database import get_db
from katalon.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.fixture
def mock_user():
    return User(
        id=uuid.uuid4(),
        email="test@example.com",
        role="admin",
        hashed_password="x",
    )


@pytest.fixture
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# POST /v1/objects/{id}/media
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_media_unsupported_type_returns_415(override_auth) -> None:
    obj_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="draft")

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(obj))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # We can't easily mock UploadFile content_type via httpx multipart,
            # so we patch the endpoint's content_type check by mocking the upload_media
            # function indirectly. Instead, we test via the actual endpoint by mocking
            # the file content_type at the FastAPI level.
            # FastAPI reads content_type from the UploadFile which comes from the request.
            # httpx sends multipart with content-type derived from filename.
            # We'll test with a .txt file which should fail.
            r = await client.post(
                f"/v1/objects/{obj_id}/media",
                files={"file": ("test.txt", b"not an image", "text/plain")},
            )
        assert r.status_code == 415
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_upload_media_object_not_found_returns_404(override_auth) -> None:
    obj_id = uuid.uuid4()

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(None))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/v1/objects/{obj_id}/media",
                files={"file": ("test.jpg", b"fake image data", "image/jpeg")},
            )
        assert r.status_code == 404
        assert "nicht gefunden" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# GET /v1/objects/{id}/media
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_media_returns_files() -> None:
    obj_id = uuid.uuid4()
    media = MediaFile(
        id=uuid.uuid4(),
        object_id=obj_id,
        filename="test.jpg",
        mime_type="image/jpeg",
        file_path="/media/test.jpg",
        status="ready",
        is_primary=True,
        media_type=None,
        created_at=datetime.now(),
    )

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_scalars_result([media]))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/objects/{obj_id}/media")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["filename"] == "test.jpg"
        assert data[0]["status"] == "ready"
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# GET /v1/objects/{id}/media/{media_id}/file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serve_media_file_not_found_returns_404() -> None:
    obj_id = uuid.uuid4()
    media_id = uuid.uuid4()

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(None))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/objects/{obj_id}/media/{media_id}/file")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# GET /v1/objects/{id}/iiif/manifest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iiif_manifest_no_ready_media_returns_404() -> None:
    obj_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="published", metadata_={})

    session = AsyncMock()
    # First execute → Object, second → MediaFile (empty), third → FieldDefinition (empty)
    session.execute = AsyncMock(side_effect=[
        _mock_result(obj),
        _mock_scalars_result([]),
        _mock_scalars_result([]),
    ])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/objects/{obj_id}/iiif/manifest")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_iiif_manifest_non_public_object_returns_404() -> None:
    obj_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="draft", metadata_={})

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(obj))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/objects/{obj_id}/iiif/manifest")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
