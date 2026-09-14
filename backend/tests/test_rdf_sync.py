# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from katalon.config import settings
from katalon.services.rdf_sync_service import (
    get_record_graph_uri,
    is_record_publicly_visible,
    rebuild_all_oxigraph,
    remove_record_from_oxigraph,
    sync_record_to_oxigraph,
)
from katalon.workers.rdf_tasks import (
    rebuild_rdf_all_task,
    remove_rdf_record_task,
    sync_rdf_record_task,
)


def test_get_record_graph_uri() -> None:
    rec_id = uuid.uuid4()
    # With base_url
    uri = get_record_graph_uri("object", rec_id, base_url="https://glam.example.org")
    assert uri == f"https://glam.example.org/objects/{rec_id}"

    # Storage location uses kebab-case route
    loc_uri = get_record_graph_uri("storage_location", rec_id, base_url="https://glam.example.org")
    assert loc_uri == f"https://glam.example.org/storage-locations/{rec_id}"

    # Without base_url falls back to URN
    urn = get_record_graph_uri("occurrence", rec_id, base_url="")
    assert urn == f"urn:katalon:occurrence:{rec_id}"


def test_is_record_publicly_visible() -> None:
    class DummyRecord:
        def __init__(self, status: str | None = None, deleted_at: datetime | None = None) -> None:
            if status is not None:
                self.status = status
            self.deleted_at = deleted_at

    # Published / public status
    assert is_record_publicly_visible(DummyRecord(status="published")) is True
    assert is_record_publicly_visible(DummyRecord(status="public")) is True

    # Draft / private status
    assert is_record_publicly_visible(DummyRecord(status="draft")) is False
    assert is_record_publicly_visible(DummyRecord(status="archived")) is False

    now = datetime.now(UTC).replace(tzinfo=None)
    assert is_record_publicly_visible(DummyRecord(status="published", deleted_at=now)) is False

    # Model without status (e.g. StorageLocation) is visible if not deleted
    assert is_record_publicly_visible(DummyRecord(deleted_at=None)) is True
    assert is_record_publicly_visible(DummyRecord(deleted_at=now)) is False


@pytest.mark.asyncio
async def test_sync_record_disabled_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oxigraph_enabled", False)
    db = AsyncMock()
    client = AsyncMock()

    res = await sync_record_to_oxigraph("object", uuid.uuid4(), db, oxigraph_client=client)
    assert res["status"] == "skipped"
    assert res["reason"] == "disabled"
    client.put_graph.assert_not_called()
    client.delete_graph.assert_not_called()


@pytest.mark.asyncio
async def test_sync_record_public_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oxigraph_enabled", True)
    monkeypatch.setattr(settings, "katalon_base_url", "https://glam.test")

    rec_id = uuid.uuid4()
    mock_record = MagicMock()
    mock_record.id = rec_id
    mock_record.status = "published"
    mock_record.deleted_at = None

    db = AsyncMock()
    mock_exec = MagicMock()
    mock_exec.scalar_one_or_none.return_value = mock_record
    db.execute.return_value = mock_exec

    client = AsyncMock()
    turtle_sample = "<https://glam.test/objects/123> a <http://example.org/Obj> ."

    with patch(
        "katalon.services.rdf_sync_service.export_single_record",
        new=AsyncMock(return_value=(turtle_sample, "text/turtle", "export.ttl")),
    ):
        res = await sync_record_to_oxigraph("object", rec_id, db, oxigraph_client=client)

    assert res["status"] == "synced"
    expected_uri = f"https://glam.test/objects/{rec_id}"
    assert res["graph_uri"] == expected_uri

    client.put_graph.assert_awaited_once_with(
        expected_uri,
        turtle_sample,
        content_type="text/turtle",
    )
    client.delete_graph.assert_not_called()


@pytest.mark.asyncio
async def test_sync_record_draft_deletes_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oxigraph_enabled", True)
    monkeypatch.setattr(settings, "katalon_base_url", "https://glam.test")

    rec_id = uuid.uuid4()
    mock_record = MagicMock()
    mock_record.id = rec_id
    mock_record.status = "draft"  # Not public
    mock_record.deleted_at = None

    db = AsyncMock()
    mock_exec = MagicMock()
    mock_exec.scalar_one_or_none.return_value = mock_record
    db.execute.return_value = mock_exec

    client = AsyncMock()
    client.delete_graph.return_value = True

    res = await sync_record_to_oxigraph("object", rec_id, db, oxigraph_client=client)
    assert res["status"] == "deleted"
    expected_uri = f"https://glam.test/objects/{rec_id}"
    assert res["graph_uri"] == expected_uri

    client.delete_graph.assert_awaited_once_with(expected_uri)
    client.put_graph.assert_not_called()


@pytest.mark.asyncio
async def test_sync_record_deleted_record_deletes_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oxigraph_enabled", True)
    rec_id = uuid.uuid4()

    mock_record = MagicMock()
    mock_record.id = rec_id
    mock_record.deleted_at = datetime.now(UTC).replace(tzinfo=None)

    db = AsyncMock()
    mock_exec = MagicMock()
    mock_exec.scalar_one_or_none.return_value = mock_record
    db.execute.return_value = mock_exec

    client = AsyncMock()
    client.delete_graph.return_value = True

    res = await sync_record_to_oxigraph("object", rec_id, db, oxigraph_client=client)
    assert res["status"] == "deleted"
    client.delete_graph.assert_awaited_once()
    client.put_graph.assert_not_called()


@pytest.mark.asyncio
async def test_sync_record_missing_deletes_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oxigraph_enabled", True)
    rec_id = uuid.uuid4()

    db = AsyncMock()
    mock_exec = MagicMock()
    mock_exec.scalar_one_or_none.return_value = None  # Record does not exist
    db.execute.return_value = mock_exec

    client = AsyncMock()
    client.delete_graph.return_value = False

    res = await sync_record_to_oxigraph("object", rec_id, db, oxigraph_client=client)
    assert res["status"] == "deleted"
    assert res["existed"] is False
    client.delete_graph.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_record_from_oxigraph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oxigraph_enabled", True)
    monkeypatch.setattr(settings, "katalon_base_url", "https://glam.test")
    rec_id = uuid.uuid4()

    client = AsyncMock()
    client.delete_graph.return_value = True

    res = await remove_record_from_oxigraph("entity", rec_id, oxigraph_client=client)
    assert res["status"] == "deleted"
    expected_uri = f"https://glam.test/entities/{rec_id}"
    assert res["graph_uri"] == expected_uri
    client.delete_graph.assert_awaited_once_with(expected_uri)


@pytest.mark.asyncio
async def test_rebuild_all_oxigraph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oxigraph_enabled", True)
    rec1 = uuid.uuid4()
    rec2 = uuid.uuid4()

    db = AsyncMock()

    # Return rec1, rec2 for objects, empty for others
    def mock_execute(query: Any) -> MagicMock:
        res = MagicMock()
        query_str = str(query)
        if "objects" in query_str:
            scalars = MagicMock()
            scalars.all.return_value = [rec1, rec2]
            res.scalars.return_value = scalars
        else:
            scalars = MagicMock()
            scalars.all.return_value = []
            res.scalars.return_value = scalars
        return res

    db.execute = AsyncMock(side_effect=mock_execute)
    client = AsyncMock()

    with patch(
        "katalon.services.rdf_sync_service.sync_record_to_oxigraph",
        new=AsyncMock(return_value={"status": "synced"}),
    ) as mock_sync:
        result = await rebuild_all_oxigraph(db, oxigraph_client=client)

    assert result["status"] == "completed"
    assert result["total_synced"] == 2
    assert result["details"]["object"] == 2
    assert mock_sync.await_count == 2


def test_celery_tasks_disabled_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oxigraph_enabled", False)

    sync_res = sync_rdf_record_task.run("object", str(uuid.uuid4()))
    assert sync_res["status"] == "skipped"

    remove_res = remove_rdf_record_task.run("object", str(uuid.uuid4()))
    assert remove_res["status"] == "skipped"

    rebuild_res = rebuild_rdf_all_task.run()
    assert rebuild_res["status"] == "skipped"


def test_celery_remove_task_handles_none_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "oxigraph_enabled", True)

    rec_id = str(uuid.uuid4())

    with patch(
        "katalon.services.rdf_sync_service.remove_record_from_oxigraph",
        new=AsyncMock(return_value={"status": "deleted"}),
    ) as mock_remove:
        res = remove_rdf_record_task.run(None, rec_id)

    assert res["status"] == "deleted"
    # Should attempt removal across all 7 types
    assert mock_remove.await_count == 7
