import uuid
from datetime import datetime

import pytest

from katalon.api.v1 import index_health
from katalon.api.v1.search import trigger_reindex_type
from katalon.core.models import Object, Procedure
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
async def test_procedure_index_doc_builds() -> None:
    proc = Procedure(
        id=uuid.uuid4(),
        idno="PRO-1",
        procedure_type="loan_out",
        status="active",
        metadata_={"label": "Leihvorgang"},
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
    )

    doc = await build_index_doc("procedure", proc)

    assert doc["record_type"] == "procedure"
    assert doc["title"] == "Leihvorgang"


@pytest.mark.asyncio
async def test_reindex_type_accepts_procedure(monkeypatch) -> None:
    calls: list[str] = []

    def fake_delay(target_type: str) -> None:
        calls.append(target_type)

    monkeypatch.setattr("katalon.workers.index_tasks.bulk_reindex_type_task.delay", fake_delay)

    result = await trigger_reindex_type("procedure")

    assert result == {"status": "queued", "target_type": "procedure"}
    assert calls == ["procedure"]


def test_index_health_counts_procedures() -> None:
    assert index_health._MODEL_MAP["procedure"] is Procedure


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
