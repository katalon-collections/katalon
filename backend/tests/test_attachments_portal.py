# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Public delivery of `file`-field attachments: /portal/v1/attachments/{id}/file."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.core.media_storage import storage_path
from katalon.core.models import Attachment, FieldDefinition, Object
from katalon.database import get_db
from katalon.main import app
from katalon.services.public_metadata_service import public_attachment_ids

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _field(name: str, field_type: str = "text", *, public: bool = True, parent=None) -> FieldDefinition:
    return FieldDefinition(
        id=uuid.uuid4(),
        target_type="object",
        name=name,
        label={},
        field_type=field_type,
        is_public=public,
        parent_id=parent.id if parent is not None else None,
    )


@pytest.fixture
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))
    return tmp_path


def _stored_attachment(record_type: str = "object", record_id: uuid.UUID | None = None) -> Attachment:
    attachment_id = uuid.uuid4()
    key = f"attachments/{attachment_id.hex[:2]}/{attachment_id}--vertrag.pdf"
    path = storage_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PDF_BYTES)
    return Attachment(
        id=attachment_id,
        record_type=record_type,
        record_id=record_id or uuid.uuid4(),
        filename="vertrag.pdf",
        mime_type="application/pdf",
        size=len(PDF_BYTES),
        storage_key=key,
    )


def _object(metadata: dict, *, status: str = "public", deleted_at=None) -> Object:
    return Object(
        id=uuid.uuid4(),
        idno="OBJ-1",
        status=status,
        object_type="artifact",
        collection_status="active",
        metadata_=metadata,
        ai_provenance={},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        deleted_at=deleted_at,
        version=1,
    )


def _session(attachment, record, fields) -> AsyncMock:
    """Mock session: `get` finds the attachment and the record only by their own ids."""
    session = AsyncMock()

    def get(model, pk):
        if model is Attachment:
            return attachment if attachment is not None and pk == attachment.id else None
        if model is Object:
            return record if record is not None and pk == record.id else None
        return None

    session.get = AsyncMock(side_effect=get)
    fields_result = MagicMock()
    fields_result.scalars.return_value.all.return_value = fields
    session.execute = AsyncMock(return_value=fields_result)
    return session


async def _get(session: AsyncMock, attachment_id: uuid.UUID):
    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(f"/portal/v1/attachments/{attachment_id}/file")
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_public_file_field_serves_file_with_nosniff(media_root) -> None:
    file_field = _field("vertrag", "file")
    attachment = _stored_attachment()
    record = _object({"vertrag": [{"id": str(attachment.id), "filename": "vertrag.pdf"}]})
    attachment.record_id = record.id
    response = await _get(_session(attachment, record, [file_field]), attachment.id)

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["cache-control"] == "no-store"
    assert response.content == PDF_BYTES


@pytest.mark.asyncio
async def test_public_group_subfield_serves_file(media_root) -> None:
    group = _field("fan_content", "group")
    file_child = _field("datei", "file", parent=group)
    attachment = _stored_attachment()
    record = _object({"fan_content": [{"datei": {"id": str(attachment.id)}}]})
    attachment.record_id = record.id
    response = await _get(
        _session(attachment, record, [group, file_child]), attachment.id
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_non_public_file_field_returns_404(media_root) -> None:
    attachment = _stored_attachment()
    record = _object({"vertrag": [{"id": str(attachment.id)}]})
    attachment.record_id = record.id
    # load_public_fields returns no field for an internal `vertrag` definition.
    response = await _get(_session(attachment, record, []), attachment.id)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_group_with_non_public_subfield_returns_404(media_root) -> None:
    group = _field("fan_content", "group")
    attachment = _stored_attachment()
    record = _object({"fan_content": [{"datei": {"id": str(attachment.id)}}]})
    attachment.record_id = record.id
    # Only the group is public; its internal `datei` subfield is not in the field list.
    response = await _get(_session(attachment, record, [group]), attachment.id)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_non_public_group_returns_404(media_root) -> None:
    attachment = _stored_attachment()
    record = _object({"fan_content": [{"datei": {"id": str(attachment.id)}}]})
    attachment.record_id = record.id
    # The group is internal, so its public child `datei` is not in the public field list.
    response = await _get(_session(attachment, record, []), attachment.id)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unpublished_record_returns_404(media_root) -> None:
    file_field = _field("vertrag", "file")
    attachment = _stored_attachment()
    record = _object({"vertrag": [{"id": str(attachment.id)}]}, status="draft")
    attachment.record_id = record.id
    response = await _get(_session(attachment, record, [file_field]), attachment.id)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_deleted_record_returns_410(media_root) -> None:
    file_field = _field("vertrag", "file")
    attachment = _stored_attachment()
    record = _object(
        {"vertrag": [{"id": str(attachment.id)}]}, deleted_at=datetime.now()
    )
    attachment.record_id = record.id
    response = await _get(_session(attachment, record, [file_field]), attachment.id)

    assert response.status_code == 410


@pytest.mark.asyncio
async def test_procedure_attachment_returns_404_without_loading_record(media_root) -> None:
    file_field = _field("vertrag", "file")
    attachment = _stored_attachment(record_type="procedure")
    session = _session(attachment, None, [file_field])
    response = await _get(session, attachment.id)

    assert response.status_code == 404
    loaded_models = [call.args[0] for call in session.get.await_args_list]
    assert loaded_models == [Attachment]


@pytest.mark.asyncio
async def test_file_removed_from_metadata_returns_404(media_root) -> None:
    file_field = _field("vertrag", "file")
    attachment = _stored_attachment()
    record = _object({"vertrag": [{"id": str(uuid.uuid4())}]})
    attachment.record_id = record.id
    response = await _get(_session(attachment, record, [file_field]), attachment.id)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_attachment_returns_404(media_root) -> None:
    response = await _get(_session(None, None, []), uuid.uuid4())

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_attachment_of_other_record_returns_404(media_root) -> None:
    """The attachment row points at a record that does not exist (or is not this one)."""
    file_field = _field("vertrag", "file")
    attachment = _stored_attachment(record_id=uuid.uuid4())
    record = _object({"vertrag": [{"id": str(attachment.id)}]})
    response = await _get(_session(attachment, record, [file_field]), attachment.id)

    assert response.status_code == 404


def test_public_attachment_ids_top_level_single_dict() -> None:
    field = _field("datei", "file")
    aid = str(uuid.uuid4())
    assert public_attachment_ids({"datei": {"id": aid}}, [field]) == {aid}


def test_public_attachment_ids_repeatable_list() -> None:
    field = _field("dateien", "file")
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    assert public_attachment_ids({"dateien": [{"id": a}, {"id": b}]}, [field]) == {a, b}


def test_public_attachment_ids_group_subfield() -> None:
    group = _field("fan_content", "group")
    child = _field("datei", "file", parent=group)
    aid = str(uuid.uuid4())
    metadata = {"fan_content": [{"titel": "x", "datei": {"id": aid}}]}
    assert public_attachment_ids(metadata, [group, child]) == {aid}


def test_public_attachment_ids_ignores_non_file_fields_and_missing_values() -> None:
    text = _field("titel", "text")
    relation = _field("bezug", "relation")
    file_field = _field("datei", "file")
    target = str(uuid.uuid4())
    metadata = {"titel": {"id": target}, "bezug": [{"id": target}], "datei": None}
    assert public_attachment_ids(metadata, [text, relation, file_field]) == set()


def test_public_attachment_ids_only_considers_given_field_defs() -> None:
    """A file id under a field that is not in field_defs (e.g. not public) is not returned."""
    aid = str(uuid.uuid4())
    assert public_attachment_ids({"intern": [{"id": aid}]}, []) == set()
    assert public_attachment_ids(None, [_field("datei", "file")]) == set()


def test_iiif_manifest_metadata_skips_file_values() -> None:
    from types import SimpleNamespace

    from katalon.integrations.cantaloupe import build_object_manifest

    title = _field("titel", "text")
    file_field = _field("vertrag", "file")
    aid = str(uuid.uuid4())
    manifest = build_object_manifest(
        "https://example.test/manifest",
        [],
        obj=SimpleNamespace(idno="OBJ-1", id=uuid.uuid4()),
        field_defs=[title, file_field],
        metadata={"titel": "Brief", "vertrag": [{"id": aid, "filename": "vertrag.pdf"}]},
    )
    assert [entry["value"] for entry in manifest["metadata"]] == [{"none": ["Brief"]}]
    assert aid not in str(manifest)
