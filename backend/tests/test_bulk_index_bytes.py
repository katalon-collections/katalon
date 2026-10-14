# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""bulk_index_documents splits _bulk requests by serialized size."""

import asyncio
import json
from typing import Any

from katalon.integrations.elasticsearch import bulk_index_documents


class _ES:
    def __init__(self, fail_ids: set[str] | None = None, raise_on: int | None = None) -> None:
        self.requests: list[list[bytes]] = []
        self.fail_ids = fail_ids or set()
        self.raise_on = raise_on

    async def bulk(self, operations: list[bytes], **_kwargs: Any) -> dict[str, Any]:
        self.requests.append(operations)
        if self.raise_on is not None and len(self.requests) == self.raise_on:
            raise ConnectionError("413 Request Entity Too Large")
        ids = [json.loads(line)["index"]["_id"] for line in operations[::2]]
        return {
            "items": [
                {"index": {"_id": i, "error": {"type": "mapper_parsing_exception"}}}
                if i in self.fail_ids
                else {"index": {"_id": i, "status": 200}}
                for i in ids
            ]
        }


def _docs(n: int, size: int) -> list[tuple[str, dict[str, Any]]]:
    return [(f"id{i}", {"title": "x" * size}) for i in range(n)]


def test_requests_stay_below_byte_limit() -> None:
    es = _ES()
    indexed, failed = asyncio.run(
        bulk_index_documents(es, "object", _docs(20, 1000), max_bytes=5000)
    )
    assert (indexed, failed) == (20, [])
    assert len(es.requests) > 1
    assert all(sum(len(line) for line in req) <= 5000 for req in es.requests)
    sent = [json.loads(line) for req in es.requests for line in req]
    assert sent[1]["record_type"] == "object"


def test_oversized_document_is_sent_alone() -> None:
    es = _ES()
    docs = [*_docs(2, 10), ("big", {"title": "y" * 20_000}), *_docs(2, 10)]
    asyncio.run(bulk_index_documents(es, "collection", docs, max_bytes=5000))
    big = [req for req in es.requests if b'"big"' in req[0]]
    assert len(big) == 1 and len(big[0]) == 2


def test_item_errors_and_failed_requests_are_reported() -> None:
    es = _ES(fail_ids={"id1"}, raise_on=2)
    indexed, failed = asyncio.run(
        bulk_index_documents(es, "object", _docs(6, 1000), max_bytes=2500)
    )
    assert "id1" in failed
    second_request_ids = [json.loads(line)["index"]["_id"] for line in es.requests[1][::2]]
    assert set(second_request_ids) <= set(failed)
    assert indexed == 6 - len(failed)
