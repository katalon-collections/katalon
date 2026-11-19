# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Attachments for the `file` field type: schema rules, upload, delivery, signed links."""

import io
import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException, UploadFile
from httpx import ASGITransport, AsyncClient
from PIL import Image

from katalon.api.v1.schema_admin import _validate_field_settings
from katalon.core.dependencies import get_current_user
from katalon.core.media_storage import storage_path
from katalon.core.models import Attachment, FieldDefinition, Object, User
from katalon.core.schemas import FieldDefinitionCreate
from katalon.database import get_db
from katalon.main import app
from katalon.services import schema_service
from katalon.services.attachment_service import (
    build_attachment_link,
    stream_upload_to_temp,
)
from katalon.services.search_service import drop_file_values

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + b"\x00" * 64
MP3_BYTES = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 64
HTML_BYTES = b"<!doctype html><html><script>alert(1)</script></html>"
SVG_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def admin_user() -> User:
    return User(id=uuid.uuid4(), email="admin@example.com", role="admin", hashed_password="x", is_active=True)


@pytest.fixture
def override_auth(admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield admin_user
    app.dependency_overrides.pop(get_current_user, None)


def _session(*, execute_value=None, get_map=None) -> AsyncMock:
    """Mock session: `execute` returns a result whose scalar_one_or_none is execute_value."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = execute_value
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    get_map = get_map or {}
    session.get = AsyncMock(side_effect=lambda model, pk: get_map.get(model))
    return session


def _use_session(session: AsyncMock) -> None:
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db


@pytest.fixture
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Schema rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_field_rejected_for_vocabulary_term_target() -> None:
    data = FieldDefinitionCreate(target_type="vocabulary_term", name="vertrag", field_type="file")
    with pytest.raises(HTTPException) as exc:
        await _validate_field_settings(AsyncMock(), data)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target_type",
    ["object", "entity", "place", "occurrence", "procedure", "collection", "storage_location"],
)
async def test_file_field_allowed_for_record_types(target_type: str) -> None:
    data = FieldDefinitionCreate(target_type=target_type, name="vertrag", field_type="file")
    await _validate_field_settings(AsyncMock(), data)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_pdf_stores_file_and_returns_metadata(override_auth, media_root) -> None:
    object_id = uuid.uuid4()
    session = _session(execute_value=Object(id=object_id))
    _use_session(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/v1/attachments/object/{object_id}",
                files={"file": ("Leihvertrag 2026.pdf", PDF_BYTES, "application/pdf")},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 201, r.text
    data = r.json()
    assert data["filename"] == "Leihvertrag 2026.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["size"] == len(PDF_BYTES)
    added = session.add.call_args.args[0]
    assert isinstance(added, Attachment)
    assert added.record_type == "object"
    assert added.record_id == object_id
    assert added.created_by == override_auth.id
    assert storage_path(added.storage_key).read_bytes() == PDF_BYTES
    assert added.storage_key.startswith("attachments/")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "data"),
    [("foto.png", _png_bytes()), ("film.mp4", MP4_BYTES), ("musik.mp3", MP3_BYTES)],
)
async def test_upload_detects_allowed_image_video_audio(
    override_auth, media_root, filename: str, data: bytes
) -> None:
    object_id = uuid.uuid4()
    _use_session(_session(execute_value=Object(id=object_id)))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/v1/attachments/object/{object_id}",
                files={"file": (filename, data, "application/octet-stream")},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_upload_html_renamed_to_pdf_is_rejected(override_auth, media_root) -> None:
    object_id = uuid.uuid4()
    _use_session(_session(execute_value=Object(id=object_id)))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/v1/attachments/object/{object_id}",
                files={"file": ("bericht.pdf", HTML_BYTES, "application/pdf")},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 415
    assert "Erlaubt sind PDF, Bild, Audio und Video" in r.json()["detail"]
    assert not list(media_root.rglob("*--*"))


@pytest.mark.asyncio
async def test_upload_svg_is_rejected(override_auth, media_root) -> None:
    object_id = uuid.uuid4()
    _use_session(_session(execute_value=Object(id=object_id)))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/v1/attachments/object/{object_id}",
                files={"file": ("logo.svg", SVG_BYTES, "image/svg+xml")},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 415


@pytest.mark.asyncio
async def test_upload_to_missing_record_returns_404(override_auth, media_root) -> None:
    _use_session(_session(execute_value=None))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/v1/attachments/object/{uuid.uuid4()}",
                files={"file": ("a.pdf", PDF_BYTES, "application/pdf")},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_upload_size_limit_returns_413_and_removes_temp_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("katalon.config.settings.attachment_max_upload_mb", 1)
    upload = UploadFile(file=io.BytesIO(PDF_BYTES + b"0" * (1024 * 1024)), filename="gross.pdf")
    with pytest.raises(HTTPException) as exc:
        await stream_upload_to_temp(upload, max_bytes=10)
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_upload_over_configured_limit_is_rejected_over_http(
    override_auth, media_root, monkeypatch
) -> None:
    monkeypatch.setattr("katalon.config.settings.attachment_max_upload_mb", 1)
    object_id = uuid.uuid4()
    _use_session(_session(execute_value=Object(id=object_id)))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/v1/attachments/object/{object_id}",
                files={"file": ("gross.pdf", PDF_BYTES + b"0" * (1024 * 1024 + 1), "application/pdf")},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_limits_endpoint_reports_configured_max_upload_mb(override_auth, monkeypatch) -> None:
    monkeypatch.setattr("katalon.config.settings.attachment_max_upload_mb", 37)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/attachments/limits")
    assert r.status_code == 200
    assert r.json() == {"max_upload_mb": 37}


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def _stored_attachment(media_root, *, mime_type: str, data: bytes, filename: str = "datei.pdf"):
    attachment_id = uuid.uuid4()
    key = f"attachments/{attachment_id.hex[:2]}/{attachment_id}--{filename}"
    path = storage_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    attachment = Attachment(
        id=attachment_id,
        record_type="object",
        record_id=uuid.uuid4(),
        filename=filename,
        mime_type=mime_type,
        size=len(data),
        storage_key=key,
    )
    return attachment


@pytest.mark.asyncio
async def test_get_file_sets_exact_type_nosniff_and_inline(override_auth, media_root) -> None:
    attachment = _stored_attachment(media_root, mime_type="application/pdf", data=PDF_BYTES)
    record = Object(id=attachment.record_id)
    _use_session(_session(execute_value=record, get_map={Attachment: attachment}))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/attachments/{attachment.id}/file")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["accept-ranges"] == "bytes"
    assert r.headers["cache-control"] == "private, no-store"
    # No sandbox, and object-src allows the browser PDF viewer (plugin content).
    csp = r.headers["content-security-policy"]
    assert "sandbox" not in csp
    assert "object-src 'self'" in csp
    assert r.content == PDF_BYTES


@pytest.mark.asyncio
async def test_get_video_file_has_sandbox_csp(override_auth, media_root) -> None:
    attachment = _stored_attachment(media_root, mime_type="video/mp4", data=MP4_BYTES, filename="film.mp4")
    record = Object(id=attachment.record_id)
    _use_session(_session(execute_value=record, get_map={Attachment: attachment}))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/attachments/{attachment.id}/file")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.headers["content-security-policy"] == "default-src 'none'; sandbox"


@pytest.mark.asyncio
async def test_get_file_range_request_returns_206(override_auth, media_root) -> None:
    data = bytes(range(100))
    attachment = _stored_attachment(media_root, mime_type="video/mp4", data=data, filename="film.mp4")
    record = Object(id=attachment.record_id)
    _use_session(_session(execute_value=record, get_map={Attachment: attachment}))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                f"/v1/attachments/{attachment.id}/file", headers={"Range": "bytes=10-19"}
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 206
    assert r.headers["content-range"] == "bytes 10-19/100"
    assert r.content == data[10:20]


@pytest.mark.asyncio
async def test_get_file_forbidden_without_read_permission(media_root, monkeypatch) -> None:
    viewer = User(id=uuid.uuid4(), email="v@example.com", role="viewer", hashed_password="x", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: viewer
    attachment = _stored_attachment(media_root, mime_type="application/pdf", data=PDF_BYTES)
    _use_session(_session(get_map={Attachment: attachment}))
    monkeypatch.setattr(
        "katalon.services.attachment_service.has_record_permission", AsyncMock(return_value=False)
    )
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/v1/attachments/{attachment.id}/file")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Signed links
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_link_then_stream_without_bearer(override_auth, media_root) -> None:
    attachment = _stored_attachment(media_root, mime_type="video/mp4", data=MP4_BYTES, filename="film.mp4")
    record = Object(id=attachment.record_id)
    session = _session(execute_value=record, get_map={Attachment: attachment, User: override_auth})
    _use_session(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            link = await client.get(f"/v1/attachments/{attachment.id}/link")
            assert link.status_code == 200
            url = link.json()["url"]
            assert url.startswith(f"/v1/attachments/{attachment.id}/stream?")
            # Stream request carries no Authorization header and no auth override applies.
            app.dependency_overrides.pop(get_current_user, None)
            r = await client.get(url)
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200
    assert r.content == MP4_BYTES
    assert r.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_stream_rejects_tampered_signature(media_root, admin_user) -> None:
    attachment = _stored_attachment(media_root, mime_type="video/mp4", data=MP4_BYTES, filename="film.mp4")
    url = build_attachment_link(attachment.id, admin_user.id)
    params = parse_qs(urlparse(url).query)
    tampered = url.replace(params["sig"][0], "0" * 64)
    session = _session(get_map={Attachment: attachment, User: admin_user})
    _use_session(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(tampered)
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_stream_rejects_expired_link(media_root, admin_user) -> None:
    attachment = _stored_attachment(media_root, mime_type="video/mp4", data=MP4_BYTES, filename="film.mp4")
    url = build_attachment_link(attachment.id, admin_user.id, now=time.time() - 1000)
    session = _session(get_map={Attachment: attachment, User: admin_user})
    _use_session(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(url)
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_stream_rejects_link_for_inactive_user(media_root, admin_user) -> None:
    attachment = _stored_attachment(media_root, mime_type="video/mp4", data=MP4_BYTES, filename="film.mp4")
    admin_user.is_active = False
    url = build_attachment_link(attachment.id, admin_user.id)
    _use_session(_session(get_map={Attachment: attachment, User: admin_user}))
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(url)
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Metadata validation and search indexing
# ---------------------------------------------------------------------------


def _file_field(name: str, *, repeatable: bool = False) -> FieldDefinition:
    return FieldDefinition(
        id=uuid.uuid4(),
        target_type="object",
        name=name,
        label={},
        field_type="file",
        is_required=False,
        is_repeatable=repeatable,
        is_translatable=False,
        settings={},
        parent_id=None,
    )


@pytest.mark.asyncio
async def test_validate_metadata_rejects_non_dict_file_value(monkeypatch) -> None:
    async def fields(db, record_type, target_subtype=None):
        return [_file_field("vertrag")]

    monkeypatch.setattr(schema_service, "get_field_definitions", fields)

    errors = await schema_service.validate_metadata(AsyncMock(), "object", {"vertrag": "abc"})
    assert any("Dateiwert muss ein Objekt mit einer Datei-ID sein" in e for e in errors)

    errors = await schema_service.validate_metadata(
        AsyncMock(), "object", {"vertrag": {"id": "keine-uuid"}}
    )
    assert any("ungültige Datei-ID" in e for e in errors)

    # A well-formed reference passes the structural check; without a record_id
    # (create) the save-time check rejects it.
    errors = await schema_service.validate_metadata(
        AsyncMock(), "object", {"vertrag": {"id": str(uuid.uuid4()), "filename": "a.pdf"}}
    )
    assert errors == [
        "Feld 'vertrag': Dateien können erst nach dem Speichern des Datensatzes hochgeladen werden."
    ]


@pytest.mark.asyncio
async def test_validate_metadata_checks_repeatable_file_list(monkeypatch) -> None:
    async def fields(db, record_type, target_subtype=None):
        return [_file_field("dokumente", repeatable=True)]

    monkeypatch.setattr(schema_service, "get_field_definitions", fields)

    errors = await schema_service.validate_metadata(
        AsyncMock(), "object", {"dokumente": {"id": str(uuid.uuid4())}}
    )
    assert any("muss eine Liste sein" in e for e in errors)

    errors = await schema_service.validate_metadata(
        AsyncMock(), "object", {"dokumente": [{"id": str(uuid.uuid4())}, "x"]}
    )
    assert any("Dateiwert muss ein Objekt mit einer Datei-ID sein" in e for e in errors)


def test_drop_file_values_removes_top_level_and_group_sub_fields() -> None:
    group = SimpleNamespace(id=uuid.uuid4(), name="fan", field_type="group", parent_id=None)
    sub_file = SimpleNamespace(id=uuid.uuid4(), name="datei", field_type="file", parent_id=group.id)
    sub_title = SimpleNamespace(id=uuid.uuid4(), name="titel", field_type="text", parent_id=group.id)
    top_file = SimpleNamespace(id=uuid.uuid4(), name="vertrag", field_type="file", parent_id=None)
    top_text = SimpleNamespace(id=uuid.uuid4(), name="titel", field_type="text", parent_id=None)
    md = {
        "vertrag": [{"id": str(uuid.uuid4()), "filename": "a.pdf"}],
        "titel": "Werk",
        "fan": [{"titel": "Premiere", "datei": {"id": str(uuid.uuid4()), "filename": "p.mp4"}}],
    }

    out = drop_file_values(md, [group, sub_file, sub_title, top_file, top_text])

    assert "vertrag" not in out
    assert out["titel"] == "Werk"
    assert out["fan"] == [{"titel": "Premiere"}]
    # The input is not mutated.
    assert "vertrag" in md


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bytes=0-9", (0, 9)),
        ("bytes=10-", (10, 99)),
        ("bytes=-5", (95, 99)),
        ("bytes=90-500", (90, 99)),
        ("bytes=5-2", None),
        ("items=0-9", None),
        ("bytes=0-4,10-14", None),
    ],
)
def test_single_byte_range_parsing(header: str, expected: tuple[int, int] | None) -> None:
    from katalon.services.attachment_service import _single_byte_range

    assert _single_byte_range(header, 100) == expected


@pytest.mark.parametrize("header", ["bytes=100-", "bytes=-0"])
def test_unsatisfiable_byte_range_returns_416(header: str) -> None:
    from katalon.services.attachment_service import _single_byte_range

    with pytest.raises(HTTPException) as exc:
        _single_byte_range(header, 100)
    assert exc.value.status_code == 416
