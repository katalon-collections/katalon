# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Public read paths accept every status in PUBLIC_STATUSES, not only "public"."""

from typing import Any

import pytest

from katalon.core.visibility import PUBLIC_STATUSES
from katalon.integrations import elasticsearch


class _CaptureES:
    def __init__(self, get_result: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.get_result = get_result

    async def search(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        body = {"hits": {"total": {"value": 0}, "hits": []}, "aggregations": {}}
        return type("Result", (), {"body": body})()

    async def get(self, **_kwargs: Any) -> dict[str, Any]:
        return self.get_result or {"found": False}


def _filters(call: dict[str, Any]) -> list[dict[str, Any]]:
    return call["body"]["query"]["bool"]["filter"]


@pytest.mark.asyncio
async def test_search_documents_accepts_status_tuple(monkeypatch) -> None:
    es = _CaptureES()
    monkeypatch.setattr(elasticsearch, "get_es", lambda: es)
    await elasticsearch.search_documents(None, None, PUBLIC_STATUSES, 0, 20)
    assert {"terms": {"status": list(PUBLIC_STATUSES)}} in _filters(es.calls[0])

    await elasticsearch.search_documents(None, None, "draft", 0, 20)
    assert {"term": {"status": "draft"}} in _filters(es.calls[-1])


@pytest.mark.asyncio
async def test_intermediate_ids_include_published(monkeypatch) -> None:
    es = _CaptureES()
    monkeypatch.setattr(elasticsearch, "get_es", lambda: es)
    await elasticsearch.search_ids_by_filter("entity", {"match_all": {}})
    assert {"terms": {"status": list(PUBLIC_STATUSES)}} in _filters(es.calls[0])


@pytest.mark.asyncio
async def test_oai_accepts_published_records(monkeypatch) -> None:
    from katalon.api.v1 import oai

    es = _CaptureES({"found": True, "_id": "x", "_source": {"status": "published"}})
    monkeypatch.setattr(elasticsearch, "get_es", lambda: es)

    result = await oai._es_search_for_oai(None, None, None, None, identifier="x")
    assert result["hits"]["total"]["value"] == 1

    await oai._es_search_for_oai(None, None, None, None)
    assert {"terms": {"status": list(PUBLIC_STATUSES)}} in _filters(es.calls[0])


@pytest.mark.asyncio
async def test_oai_get_record_still_hides_drafts(monkeypatch) -> None:
    from katalon.api.v1 import oai

    es = _CaptureES({"found": True, "_id": "x", "_source": {"status": "draft"}})
    monkeypatch.setattr(elasticsearch, "get_es", lambda: es)
    result = await oai._es_search_for_oai(None, None, None, None, identifier="x")
    assert result["hits"]["total"]["value"] == 0
