# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Tests for media upload API endpoints."""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.api.v1.media import _serialize
from katalon.core.dependencies import get_current_user, try_get_current_user
from katalon.core.media_storage import storage_key, storage_path
from katalon.core.media_validation import PIL_MIME_BY_FORMAT
from katalon.core.models import MediaFile, Object, User
from katalon.database import get_db
from katalon.main import app
from katalon.services.attachment_service import build_attachment_link, build_signed_query

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
        storage_key="ab/test.jpg",
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
        storage_key="ab/test.jpg",
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
        # Portal builds the thumbnail URL from it without the redirect route.
        assert data[0]["iiif_identifier"] == "ab%2Ftest.jpg"
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
        storage_key="ab/test.jpg",
        status="ready",
        is_primary=True,
        created_at=datetime.now(),
    )
    old_stamp = datetime(2020, 1, 1)
    obj = MagicMock(updated_at=old_stamp)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(media_file))
    session.add = MagicMock()
    session.get = AsyncMock(return_value=obj)
    reindex = AsyncMock()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("katalon.api.v1.media._reindex_object", reindex):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.patch(
                    f"/v1/objects/{obj_id}/media/{media_id}",
                    json={
                        "license_uri": "https://creativecommons.org/licenses/by/4.0/",
                        "rights_holder": {"name": "Museum", "uri": "https://example.org/museum"},
                        "credit_line": "  Veröffentlichung genehmigt.  ",
                    },
                )
        assert response.status_code == 200
        assert response.json()["rights_holder"]["name"] == "Museum"
        assert response.json()["credit_line"] == "Veröffentlichung genehmigt."
        assert media_file.license_uri.endswith("/by/4.0/")
        # Rights are part of the object's export: datestamp moves, index is refreshed.
        assert obj.updated_at > old_stamp
        reindex.assert_awaited_once()
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
        storage_key=f"{media_id.hex[:2]}/{media_id}--test.tif",
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
        assert response.headers["location"].endswith(
            f"/iiif/3/{media_id.hex[:2]}%2F{media_id}--test.tif/full/,300/0/default.jpg"
        )
        # Cacheable in the browser only: every /iiif/ fetch is still authorized.
        assert response.headers["cache-control"] == "private, max-age=2592000"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_portal_media_list_denied_for_staff_without_object_read_permission() -> None:
    """Regression test: a logged-in staff user whose role has no `read`
    permission on `object` must be treated as anonymous for media/IIIF access —
    not automatically granted full visibility just for being authenticated."""
    obj_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="internal", metadata_={})
    no_permission_user = User(
        id=uuid.uuid4(), email="editor@example.com", role="editor", hashed_password="x"
    )

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _mock_result(obj),
        _mock_result(None),  # no matching role_permissions row -> read denied
    ])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[try_get_current_user] = lambda: no_permission_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{obj_id}/media")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_portal_media_file_denied_for_staff_without_object_read_permission() -> None:
    obj_id = uuid.uuid4()
    media_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="internal", metadata_={})
    no_permission_user = User(
        id=uuid.uuid4(), email="editor@example.com", role="editor", hashed_password="x"
    )

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _mock_result(obj),
        _mock_result(None),  # no matching role_permissions row -> read denied
    ])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[try_get_current_user] = lambda: no_permission_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{obj_id}/media/{media_id}/file")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_portal_media_thumbnail_denied_for_staff_without_object_read_permission() -> None:
    obj_id = uuid.uuid4()
    media_id = uuid.uuid4()
    obj = Object(id=obj_id, idno="OBJ-001", status="internal", metadata_={})
    no_permission_user = User(
        id=uuid.uuid4(), email="editor@example.com", role="editor", hashed_password="x"
    )

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _mock_result(obj),
        _mock_result(None),  # no matching role_permissions row -> read denied
    ])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[try_get_current_user] = lambda: no_permission_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{obj_id}/media/{media_id}/thumbnail")
        assert response.status_code == 404
        assert "cache-control" not in response.headers
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_iiif_authorize_denied_for_staff_without_object_read_permission() -> None:
    """Regression test for the nginx auth_request endpoint backing Cantaloupe:
    a logged-in staff user without `read` permission on `object` must be
    refused access to an internal object's IIIF image, same as anonymous."""
    obj_id = uuid.uuid4()
    media = MediaFile(
        id=uuid.uuid4(),
        object_id=obj_id,
        filename="test.jpg",
        mime_type="image/jpeg",
        storage_key="ab/test.jpg",
        iiif_storage_key="ab/test.jpg",
        status="ready",
        is_public=True,
        created_at=datetime.now(),
    )
    obj = Object(id=obj_id, idno="OBJ-001", status="internal", metadata_={})
    no_permission_user = User(
        id=uuid.uuid4(), email="editor@example.com", role="editor", hashed_password="x"
    )

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[
        _mock_result(media),
        _mock_result(None),  # no matching role_permissions row -> read denied
    ])
    session.get = AsyncMock(return_value=obj)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[try_get_current_user] = lambda: no_permission_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/media/_authorize",
                headers={"X-Original-Uri": "/iiif/3/ab%2Ftest.jpg/full/,300/0/default.jpg"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(("is_public", "expected"), [(True, 200), (False, 403)])
async def test_iiif_authorize_accepts_ingress_nginx_original_url(
    is_public: bool, expected: int
) -> None:
    """ingress-nginx auth-url (Helm chart) sends X-Original-URL, not X-Original-URI."""
    obj_id = uuid.uuid4()
    media = MediaFile(
        id=uuid.uuid4(),
        object_id=obj_id,
        filename="test.jpg",
        mime_type="image/jpeg",
        storage_key="ab/test.jpg",
        iiif_storage_key="ab/test.jpg",
        status="ready",
        is_public=is_public,
        created_at=datetime.now(),
    )
    obj = Object(id=obj_id, idno="OBJ-001", status="published", metadata_={})

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(media))
    session.get = AsyncMock(return_value=obj)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[try_get_current_user] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/media/_authorize",
                headers={
                    "X-Original-Url": "http://katalon.local/iiif/3/ab%2Ftest.jpg/full/,300/0/default.jpg"
                },
            )
        assert response.status_code == expected
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("viewer", "object_status", "media_public", "expected"),
    [
        ("anonymous", "published", True, "public"),
        ("admin", "public", True, "public"),
        # Staff fetching internal media / media of an internal object: never shared-cacheable.
        ("admin", "public", False, "restricted"),
        ("admin", "internal", True, "restricted"),
    ],
)
async def test_iiif_authorize_reports_media_visibility_for_nginx_cache_control(
    viewer: str, object_status: str, media_public: bool, expected: str
) -> None:
    obj_id = uuid.uuid4()
    media = MediaFile(
        id=uuid.uuid4(), object_id=obj_id, filename="test.jpg", mime_type="image/jpeg",
        storage_key="ab/test.jpg", iiif_storage_key="ab/test.jpg", status="ready",
        is_public=media_public, created_at=datetime.now(),
    )
    obj = Object(id=obj_id, idno="OBJ-001", status=object_status, metadata_={})
    user = None if viewer == "anonymous" else User(
        id=uuid.uuid4(), email="admin@example.com", role="admin", hashed_password="x"
    )

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(media))
    session.get = AsyncMock(return_value=obj)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[try_get_current_user] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/v1/media/_authorize",
                headers={"X-Original-Uri": "/iiif/3/ab%2Ftest.jpg/full/,300/0/default.jpg"},
            )
        assert response.status_code == 200
        assert response.headers["x-media-visibility"] == expected
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)


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


@pytest.mark.asyncio
async def test_direct_media_download_by_id_public_success(tmp_path, monkeypatch) -> None:
    media_id = uuid.uuid4()
    obj_id = uuid.uuid4()
    obj = Object(
        id=obj_id,
        idno="OBJ-001",
        status="public",
        collection_status="active",
        metadata_={},
    )
    test_file = tmp_path / "test.jpg"
    test_file.write_bytes(b"dummy jpeg content")

    from katalon.core.media_storage import LocalStorage

    storage = LocalStorage()
    monkeypatch.setattr("katalon.api.v1.media.get_storage", lambda: storage)
    monkeypatch.setattr(storage, "local_path", lambda key: test_file)

    mf = MediaFile(
        id=media_id,
        object_id=obj_id,
        filename="specimen.jpg",
        mime_type="image/jpeg",
        storage_key="dummy.jpg",
        status="ready",
        is_public=True,
        created_at=datetime.now(),
    )

    session = AsyncMock()
    # First execute is for MediaFile, second is for Object
    session.execute = AsyncMock(side_effect=[_mock_result(mf), _mock_result(obj)])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Test /v1/media/{id}/download
            r = await client.get(f"/v1/media/{media_id}/download")
            assert r.status_code == 200
            assert 'filename="specimen.jpg"' in r.headers.get("content-disposition", "")
            assert r.content == b"dummy jpeg content"

            # Reset side effect for next call
            session.execute = AsyncMock(side_effect=[_mock_result(mf), _mock_result(obj)])
            # Test /api/v1/media/{id}/download
            r_api = await client.get(f"/api/v1/media/{media_id}/download")
            assert r_api.status_code == 200

            # Reset side effect for portal call
            session.execute = AsyncMock(side_effect=[_mock_result(mf), _mock_result(obj)])
            # Test /portal/v1/media/{id}/download
            r_portal = await client.get(f"/portal/v1/media/{media_id}/download")
            assert r_portal.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_direct_media_download_draft_object_returns_404_for_anonymous() -> None:
    media_id = uuid.uuid4()
    obj_id = uuid.uuid4()
    obj = Object(
        id=obj_id,
        idno="OBJ-001",
        status="draft",
        collection_status="active",
        metadata_={},
    )
    mf = MediaFile(
        id=media_id,
        object_id=obj_id,
        filename="specimen.jpg",
        mime_type="image/jpeg",
        storage_key="dummy.jpg",
        status="ready",
        is_public=True,
        created_at=datetime.now(),
    )

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_mock_result(mf), _mock_result(obj)])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/media/{media_id}/download")
            assert r.status_code == 404
            assert r.json() == {"detail": "Objekt nicht gefunden"}
    finally:
        app.dependency_overrides.pop(get_db, None)



@pytest.mark.asyncio
async def test_delete_media_moves_object_datestamp(override_auth) -> None:
    obj_id = uuid.uuid4()
    media_id = uuid.uuid4()
    media_file = MediaFile(
        id=media_id, object_id=obj_id, filename="test.jpg", mime_type="image/jpeg",
        storage_key="ab/test.jpg", status="ready", is_primary=True, created_at=datetime.now(),
    )
    old_stamp = datetime(2020, 1, 1)
    obj = MagicMock(updated_at=old_stamp)
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_mock_result(media_file))
    session.add = MagicMock()
    session.get = AsyncMock(return_value=obj)
    reindex = AsyncMock()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with (
            patch("katalon.api.v1.media._reindex_object", reindex),
            patch("katalon.api.v1.media.finalize_pending_delete", AsyncMock(return_value=False)),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.delete(f"/v1/objects/{obj_id}/media/{media_id}")
        assert response.status_code == 204
        # A removed image leaves the export: incremental harvests must see the object again.
        assert obj.updated_at > old_stamp
        reindex.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# File delivery headers and signed media links
# ---------------------------------------------------------------------------

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + b"\x00" * 64
CSP_SANDBOX = "default-src 'none'; sandbox"
CSP_PDF = "default-src 'none'; object-src 'self'; frame-ancestors 'self'"


@pytest.fixture
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))
    return tmp_path


@pytest.fixture
def media_user() -> User:
    return User(id=uuid.uuid4(), email="media@example.com", role="admin", hashed_password="x", is_active=True)


@pytest.fixture
def signed_in(media_user):
    app.dependency_overrides[get_current_user] = lambda: media_user
    app.dependency_overrides[try_get_current_user] = lambda: media_user
    yield media_user
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(try_get_current_user, None)


def _stored_media(media_root, *, obj_id: uuid.UUID, mime_type: str, data: bytes, filename: str) -> MediaFile:
    media_id = uuid.uuid4()
    key = storage_key(media_id, filename)
    path = storage_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return MediaFile(
        id=media_id,
        object_id=obj_id,
        filename=filename,
        mime_type=mime_type,
        storage_key=key,
        status="ready",
        is_public=True,
        is_primary=True,
        created_at=datetime.now(),
    )


def _use_media_session(*results, user: User | None = None) -> None:
    """Session whose execute() returns the given results in order (object, then media)."""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_mock_result(value) for value in results])
    session.get = AsyncMock(return_value=user)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db


@pytest.mark.asyncio
async def test_media_video_file_is_nosniff_and_sandboxed(signed_in, media_root) -> None:
    obj = Object(id=uuid.uuid4(), idno="OBJ-V", status="published", metadata_={})
    media = _stored_media(media_root, obj_id=obj.id, mime_type="video/mp4", data=MP4_BYTES, filename="film.mp4")
    _use_media_session(obj, media)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/objects/{obj.id}/media/{media.id}/file")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-security-policy"] == CSP_SANDBOX


@pytest.mark.asyncio
async def test_media_pdf_file_gets_pdf_csp(signed_in, media_root) -> None:
    obj = Object(id=uuid.uuid4(), idno="OBJ-P", status="published", metadata_={})
    media = _stored_media(media_root, obj_id=obj.id, mime_type="application/pdf", data=PDF_BYTES, filename="brief.pdf")
    _use_media_session(obj, media)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/objects/{obj.id}/media/{media.id}/file")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-security-policy"] == CSP_PDF
    assert r.headers["content-disposition"].startswith("inline")


@pytest.mark.asyncio
async def test_media_link_then_stream_without_bearer(signed_in, media_user, media_root) -> None:
    obj = Object(id=uuid.uuid4(), idno="OBJ-L", status="published", metadata_={})
    media = _stored_media(media_root, obj_id=obj.id, mime_type="video/mp4", data=MP4_BYTES, filename="film.mp4")
    _use_media_session(obj, media)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            link = await client.get(f"/v1/objects/{obj.id}/media/{media.id}/link")
            assert link.status_code == 200
            url = link.json()["url"]
            assert url.startswith(f"/v1/objects/{obj.id}/media/{media.id}/stream?")

            # No bearer and no auth overrides: the signed link is the only credential.
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(try_get_current_user, None)
            _use_media_session(obj, media, user=media_user)
            r = await client.get(url)
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200
    assert r.content == MP4_BYTES
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-security-policy"] == CSP_SANDBOX


@pytest.mark.asyncio
async def test_media_stream_rejects_tampered_signature(media_user, media_root) -> None:
    obj_id = uuid.uuid4()
    media = _stored_media(media_root, obj_id=obj_id, mime_type="video/mp4", data=MP4_BYTES, filename="film.mp4")
    query = build_signed_query(media.id, media_user.id, scope="media")
    tampered = f"/v1/objects/{obj_id}/media/{media.id}/stream?" + query.replace(
        parse_qs(query)["sig"][0], "0" * 64
    )
    _use_media_session(Object(id=obj_id, status="published"), media)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(tampered)
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_media_stream_rejects_attachment_scoped_signature(media_user, media_root) -> None:
    obj_id = uuid.uuid4()
    media = _stored_media(media_root, obj_id=obj_id, mime_type="video/mp4", data=MP4_BYTES, filename="film.mp4")
    # Same user, same resource id, but issued for attachments: must not open the media file.
    attachment_url = build_attachment_link(media.id, media_user.id)
    media_url = attachment_url.replace(
        f"/v1/attachments/{media.id}/stream", f"/v1/objects/{obj_id}/media/{media.id}/stream"
    )
    _use_media_session(Object(id=obj_id, status="published"), media)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(media_url)
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 403
