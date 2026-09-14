# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.integrations.elasticsearch import (
    DEFAULT_REINDEX_BATCH_SIZE,
    ReindexBatchError,
    reindex_type,
)


@pytest.fixture
def fake_es(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    es = MagicMock()
    es.delete_by_query = AsyncMock(return_value={"deleted": 0})
    es.bulk = AsyncMock(return_value={"items": []})
    es.indices = MagicMock()
    es.indices.refresh = AsyncMock(return_value={"_shards": {"total": 1, "successful": 1}})
    es.close = AsyncMock()
    monkeypatch.setattr("katalon.integrations.elasticsearch.get_es", lambda: es)
    return es


@pytest.mark.asyncio
async def test_reindex_type_batches_records(fake_es: MagicMock) -> None:
    """Verify that records are chunked into multiple es.bulk calls according to batch_size."""
    records = [(f"doc_{i}", {"title": f"Record {i}"}) for i in range(1250)]

    indexed = await reindex_type("object", records, batch_size=500)

    assert indexed == 1250
    fake_es.delete_by_query.assert_awaited_once()
    assert fake_es.bulk.await_count == 3

    # Check batch sizes: 500, 500, 250 (each record has 2 ops: index action + body)
    calls = fake_es.bulk.await_args_list
    assert len(calls[0].kwargs["body"]) == 1000  # 500 docs * 2
    assert len(calls[1].kwargs["body"]) == 1000  # 500 docs * 2
    assert len(calls[2].kwargs["body"]) == 500  # 250 docs * 2

    # Verify refresh was called at the end
    fake_es.indices.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_reindex_type_small_record_type(fake_es: MagicMock) -> None:
    """Verify that small record types (< batch_size) work transparently in 1 batch."""
    records = [(f"doc_{i}", {"title": f"Small {i}"}) for i in range(5)]

    indexed = await reindex_type("collection", records, batch_size=500)

    assert indexed == 5
    fake_es.delete_by_query.assert_awaited_once()
    assert fake_es.bulk.await_count == 1
    assert len(fake_es.bulk.await_args_list[0].kwargs["body"]) == 10  # 5 docs * 2
    fake_es.indices.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_reindex_type_empty_records(fake_es: MagicMock) -> None:
    """Verify that empty records list deletes existing docs and returns 0 without calling bulk."""
    indexed = await reindex_type("storage_location", [])

    assert indexed == 0
    fake_es.delete_by_query.assert_awaited_once()
    assert fake_es.bulk.await_count == 0
    fake_es.indices.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_reindex_type_invalid_batch_size() -> None:
    """Verify that batch_size <= 0 raises ValueError."""
    with pytest.raises(ValueError, match="batch_size must be positive"):
        await reindex_type("object", [("id1", {})], batch_size=0)

    with pytest.raises(ValueError, match="batch_size must be positive"):
        await reindex_type("object", [("id1", {})], batch_size=-10)


@pytest.mark.asyncio
async def test_reindex_type_handles_batch_failure_with_diagnostics(fake_es: MagicMock) -> None:
    """When a batch raises an exception, other batches still process, refresh is called,
    and ReindexBatchError is raised identifying the failing batch and record IDs."""
    records = [(f"doc_{i}", {"title": f"Record {i}"}) for i in range(15)]

    # Batch 2 fails (indices 5-9)
    async def bulk_mock(body: list[Any], refresh: bool = False) -> dict[str, Any]:
        first_id = body[0]["index"]["_id"]
        if first_id == "doc_5":
            raise RuntimeError("Elasticsearch 413 payload too large")
        return {
            "items": [{"index": {"_id": body[i]["index"]["_id"]}} for i in range(0, len(body), 2)]
        }

    fake_es.bulk.side_effect = bulk_mock

    with pytest.raises(ReindexBatchError) as exc_info:
        await reindex_type("object", records, batch_size=5)

    err = exc_info.value
    assert err.target_type == "object"
    assert err.indexed_count == 10  # batch 1 (5) + batch 3 (5)
    assert len(err.failed_batches) == 1
    failed = err.failed_batches[0]
    assert failed["batch"] == 2
    assert "doc_5" in failed["doc_ids"]
    assert "doc_9" in failed["doc_ids"]
    assert "Elasticsearch 413" in failed["error"]

    # All 3 batches were attempted
    assert fake_es.bulk.await_count == 3
    # Refresh was still called to preserve successfully indexed records
    fake_es.indices.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_reindex_type_handles_item_level_errors(fake_es: MagicMock) -> None:
    """When individual documents fail within a batch, they are identified and deducted."""
    records = [("doc_1", {}), ("doc_2", {}), ("doc_3", {})]

    fake_es.bulk.return_value = {
        "items": [
            {"index": {"_id": "doc_1", "status": 200}},
            {
                "index": {
                    "_id": "doc_2",
                    "status": 400,
                    "error": {"type": "mapper_parsing_exception", "reason": "bad value"},
                }
            },
            {"index": {"_id": "doc_3", "status": 200}},
        ]
    }

    with pytest.raises(ReindexBatchError) as exc_info:
        await reindex_type("entity", records, batch_size=10)

    err = exc_info.value
    assert err.indexed_count == 2
    assert len(err.failed_batches) == 1
    assert "doc_2" in err.failed_batches[0]["doc_ids"]


@pytest.mark.asyncio
async def test_reindex_type_raise_on_error_false(fake_es: MagicMock) -> None:
    """When raise_on_error=False, errors are logged and partial count is returned."""
    records = [(f"doc_{i}", {}) for i in range(10)]

    async def bulk_mock(body: list[Any], refresh: bool = False) -> dict[str, Any]:
        first_id = body[0]["index"]["_id"]
        if first_id == "doc_0":
            raise RuntimeError("Transient network issue")
        return {"items": []}

    fake_es.bulk.side_effect = bulk_mock

    indexed = await reindex_type("object", records, batch_size=5, raise_on_error=False)

    assert indexed == 5
    assert fake_es.bulk.await_count == 2
    fake_es.indices.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_reindex_type_respects_default_batch_size(
    monkeypatch: pytest.MonkeyPatch, fake_es: MagicMock
) -> None:
    """Verify DEFAULT_REINDEX_BATCH_SIZE is used when batch_size is not provided."""
    records = [(f"doc_{i}", {}) for i in range(1001)]

    indexed = await reindex_type("place", records)

    assert indexed == 1001
    # With default 500, 1001 records should result in 3 batches (500, 500, 1)
    assert fake_es.bulk.await_count == 3
    assert DEFAULT_REINDEX_BATCH_SIZE == 500
