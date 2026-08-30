"""Tests for media upload API endpoints."""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.api.v1.media import _serialize
from katalon.core.dependencies import get_current_user
from katalon.core.media_validation import PIL_MIME_BY_FORMAT
from katalon.core.models import MediaFile, Object, User
from katalon.database import get_db
from katalon.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_mpo_images_are_stored_as_jpeg() -> None:
    assert PIL_MIME_BY_FORMAT["MPO"] == "image/jpeg"


def _mock_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def test_media_license_link_requires_absolute_http_url() -> None:
    media = MediaFile(
        id=uuid.uuid4(),
        object_id=uuid.uuid4(),
        filename="test.jpg",
        mime_type="image/jpeg",
        file_path="/media/test.jpg",
        status="ready",
        created_at=datetime.now(),
        license_uri="javascript:alert(1)",
    )
    assert "license" not in _serialize(media)["_links"]

    media.license_uri = "https://creativecommons.org/licenses/by/4.0/"
    assert _serialize(media)["_links"]["license"] == {"href": media.license_uri}


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
    obj = Object(id=obj_id, idno="OBJ-001", status="published", metadata_={})
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
    session.execute = AsyncMock(side_effect=[
        _mock_result(obj),
        _mock_scalars_result([media]),
    ])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/portal/v1/objects/{obj_id}/media")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["filename"] == "test.jpg"
        assert data[0]["status"] == "ready"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_portal_list_media_requests_only_ready_files() -> None:
    obj_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="published", metadata_={})
    session = AsyncMock()
    statements: list[str] = []

    async def execute(statement):
        statements.append(str(statement))
        return _mock_result(obj) if len(statements) == 1 else _mock_scalars_result([])

    session.execute.side_effect = execute

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{obj_id}/media")
        assert response.status_code == 200
        assert "media_files.status = :status_1" in statements[1]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_patch_media_rights(override_auth) -> None:
    obj_id = uuid.uuid4()
    media_id = uuid.uuid4()
    media_file = MediaFile(
        id=media_id,
        object_id=obj_id,
        filename="test.jpg",
        mime_type="image/jpeg",
        file_path="/media/test.jpg",
        status="ready",
        is_primary=True,
        created_at=datetime.now(),
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(media_file))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch(
                f"/v1/objects/{obj_id}/media/{media_id}",
                json={
                    "license_uri": "https://creativecommons.org/licenses/by/4.0/",
                    "rights_holder": {"name": "Museum", "uri": "https://example.org/museum"},
                },
            )
        assert response.status_code == 200
        assert response.json()["rights_holder"]["name"] == "Museum"
        assert media_file.license_uri.endswith("/by/4.0/")
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# GET /v1/objects/{id}/media/{media_id}/file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serve_media_file_not_found_returns_404() -> None:
    obj_id = uuid.uuid4()
    media_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="published", metadata_={})

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _mock_result(obj),
        _mock_result(None),
    ])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/portal/v1/objects/{obj_id}/media/{media_id}/file")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_portal_media_file_requests_only_ready_files() -> None:
    obj_id = uuid.uuid4()
    media_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="published", metadata_={})
    session = AsyncMock()
    statements: list[str] = []

    async def execute(statement):
        statements.append(str(statement))
        return _mock_result(obj) if len(statements) == 1 else _mock_result(None)

    session.execute.side_effect = execute

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{obj_id}/media/{media_id}/file")
        assert response.status_code == 404
        assert "media_files.status = :status_1" in statements[1]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_portal_media_thumbnail_redirects_to_iiif() -> None:
    obj_id = uuid.uuid4()
    media_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="published", metadata_={})
    media = MediaFile(
        id=media_id,
        object_id=obj_id,
        filename="test.tif",
        mime_type="image/tiff",
        file_path=f"/media/{media_id}.tif",
        status="ready",
        created_at=datetime.now(),
    )
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_mock_result(obj), _mock_result(media)])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{obj_id}/media/{media_id}/thumbnail")
        assert response.status_code == 307
        assert response.headers["location"].endswith(f"/iiif/3/{media_id}.tif/full/,300/0/default.jpg")
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
            r = await client.get(f"/portal/v1/objects/{obj_id}/iiif/manifest")
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
            r = await client.get(f"/portal/v1/objects/{obj_id}/iiif/manifest")
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_portal_iiif_manifest_inactive_collection_returns_404() -> None:
    obj_id = uuid.uuid4()
    obj = Object(
        id=obj_id,
        idno="OBJ-001",
        status="published",
        collection_status="inactive",
        metadata_={},
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(obj))

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{obj_id}/iiif/manifest")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
