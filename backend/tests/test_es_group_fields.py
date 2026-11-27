# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Group sub-field values must never cost a record its index document.

A text value ("640 KB") next to an old long-typed dynamic mapping made Elasticsearch reject
the whole document (min_ram on the staging instance).
"""

import asyncio
import json
from typing import Any

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders, NodeConfig
from elasticsearch import BadRequestError

import katalon.integrations.elasticsearch as es_module
from katalon.integrations.elasticsearch import INDEX_SETTINGS, bulk_index_documents


def _parse_error() -> BadRequestError:
    meta = ApiResponseMeta(
        status=400, http_version="1.1", headers=HttpHeaders(), duration=0.0,
        node=NodeConfig("http", "localhost", 9200),
    )
    body = {"error": {"type": "document_parsing_exception", "reason": "failed to parse field"}}
    return BadRequestError("document_parsing_exception", meta, body)


def test_group_instances_are_not_dynamically_mapped() -> None:
    assert INDEX_SETTINGS["mappings"]["date_detection"] is False
    templates = INDEX_SETTINGS["mappings"]["dynamic_templates"]
    group = next(t["group_fields"] for t in templates if "group_fields" in t)
    assert group["mapping"] == {"type": "nested", "dynamic": False}


def test_bce_dates_in_group_subfields_are_indexed_and_fallback_safe() -> None:
    from datetime import datetime
    from types import SimpleNamespace

    from katalon.services import search_service

    record = SimpleNamespace(
        idno="OBJ-BCE-GRP",
        status="public",
        object_type="coin",
        collection_status="active",
        metadata_={
            "title": "Antike Münze",
            "events": [
                {"event_date": "-0043-06-15", "note": "Prägung"},
                {"event_date": "0000-02-29", "note": "Fundkontext"},
            ],
        },
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
    )

    doc = search_service._build_doc(
        "object", record, searchable_fields={"title", "events"}, group_fields={"events"}
    )
    assert doc["grp_events"] == record.metadata_["events"]
    assert "-0043-06-15" in doc["search_text"]
    assert "0000-02-29" in doc["search_text"]

    es = _BulkES()
    indexed, failed = asyncio.run(bulk_index_documents(es, "object", [("bce-1", doc)]))
    assert (indexed, failed) == (1, [])
    assert all(not key.startswith("grp_") for key in es.requests[1][1])
    assert "-0043-06-15" in es.requests[1][1]["search_text"]


class _BulkES:
    """Rejects every document that carries grp_* keys, like a long-typed old mapping."""

    def __init__(self) -> None:
        self.requests: list[list[dict[str, Any]]] = []

    async def bulk(self, operations: list[bytes], **_kwargs: Any) -> dict[str, Any]:
        parsed = [json.loads(line) for line in operations]
        self.requests.append(parsed)
        items = []
        for action, source in zip(parsed[::2], parsed[1::2], strict=True):
            doc_id = action["index"]["_id"]
            bad = any(key.startswith("grp_") for key in source)
            items.append(
                {"index": {"_id": doc_id, "error": {"type": "document_parsing_exception"}}}
                if bad
                else {"index": {"_id": doc_id, "status": 200}}
            )
        return {"items": items}


def test_bulk_retries_rejected_documents_without_group_fields() -> None:
    es = _BulkES()
    docs = [
        ("a", {"title": "A", "grp_systemanforderungen": [{"min_ram": "640 KB"}]}),
        ("b", {"title": "B"}),
    ]
    indexed, failed = asyncio.run(bulk_index_documents(es, "occurrence", docs))
    assert (indexed, failed) == (2, [])
    retry = es.requests[1]
    assert [action["index"]["_id"] for action in retry[::2]] == ["a"]
    assert all(not key.startswith("grp_") for key in retry[1])
    assert retry[1]["title"] == "A"


def test_bulk_does_not_retry_documents_without_group_fields() -> None:
    class _Always(_BulkES):
        async def bulk(self, operations: list[bytes], **_kwargs: Any) -> dict[str, Any]:
            self.requests.append([json.loads(line) for line in operations])
            return {"items": [{"index": {"_id": "x", "error": {"type": "mapper_parsing_exception"}}}]}

    es = _Always()
    indexed, failed = asyncio.run(bulk_index_documents(es, "object", [("x", {"title": "X"})]))
    assert (indexed, failed) == (0, ["x"])
    assert len(es.requests) == 1


class _SingleES:
    def __init__(self) -> None:
        self.bodies: list[dict[str, Any]] = []

    async def index(self, *, index: str, id: str, body: dict[str, Any], refresh: bool) -> None:
        self.bodies.append(body)
        if any(key.startswith("grp_") for key in body):
            raise _parse_error()


def test_index_document_falls_back_to_a_document_without_group_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    es = _SingleES()

    async def no_shadow() -> None:
        return None

    monkeypatch.setattr(es_module, "get_es", lambda: es)
    monkeypatch.setattr(es_module, "_shadow_index", no_shadow)
    asyncio.run(es_module.index_document("a", {"title": "A", "grp_x": [{"min_ram": "640 KB"}]}))
    assert es.bodies == [{"title": "A", "grp_x": [{"min_ram": "640 KB"}]}, {"title": "A"}]


def test_index_document_still_raises_other_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    es = _SingleES()

    async def no_shadow() -> None:
        return None

    monkeypatch.setattr(es_module, "get_es", lambda: es)
    monkeypatch.setattr(es_module, "_shadow_index", no_shadow)
    with pytest.raises(BadRequestError):
        # No group fields to drop: the error is not ours to hide.
        class _Plain(_SingleES):
            async def index(self, *, index: str, id: str, body: dict[str, Any], refresh: bool) -> None:
                raise _parse_error()

        monkeypatch.setattr(es_module, "get_es", lambda: _Plain())
        asyncio.run(es_module.index_document("a", {"title": "A"}))
