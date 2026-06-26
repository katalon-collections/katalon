import uuid
from datetime import datetime

import pytest

from katalon.core.models import Object
from katalon.integrations import elasticsearch
from katalon.services.search_service import build_index_doc


@pytest.mark.asyncio
async def test_object_index_doc_includes_collection_status() -> None:
    obj = Object(
        id=uuid.uuid4(),
        idno="OBJ-1",
        status="public",
        collection_status="on_loan_out",
        metadata_={"title": "Test"},
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
    )

    doc = await build_index_doc("object", obj)

    assert doc["collection_status"] == "on_loan_out"


@pytest.mark.asyncio
async def test_search_documents_keeps_only_active_public_objects(monkeypatch) -> None:
    captured: dict = {}

    class FakeES:
        async def search(self, **kwargs):
            captured.update(kwargs)
            return type("Result", (), {"body": {"hits": {"total": {"value": 0}, "hits": []}, "aggregations": {}}})()

    monkeypatch.setattr(elasticsearch, "get_es", lambda: FakeES())

    await elasticsearch.search_documents(None, None, "public", 0, 20, active_objects_only=True)

    filters = captured["body"]["query"]["bool"]["filter"]
    assert {"term": {"status": "public"}} in filters
    assert {
        "bool": {
            "should": [
                {"bool": {"must_not": {"term": {"record_type": "object"}}}},
                {"term": {"collection_status": "active"}},
            ],
            "minimum_should_match": 1,
        }
    } in filters
