import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from katalon.api.v1 import index_health
from katalon.api.v1.search import trigger_reindex_type
from katalon.core.models import Object, Occurrence, Procedure, Relation
from katalon.integrations import elasticsearch
from katalon.services import search_service
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
async def test_index_doc_embeds_and_facets_inherited_relation_fields() -> None:
    object_id = uuid.uuid4()
    occurrence_id = uuid.uuid4()
    obj = Object(
        id=object_id, idno="OBJ-1", status="public", collection_status="active",
        metadata_={"title": "Objekt"}, created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 2),
    )
    occurrence = Occurrence(
        id=occurrence_id, idno="OCC-1", occurrence_type="work", status="public",
        metadata_={"title": "Werk", "publication_year": "1905"},
    )
    relation = Relation(
        id=uuid.uuid4(), from_type="object", from_id=object_id,
        to_type="occurrence", to_id=occurrence_id, relation_type="is_edition_of",
    )

    class Result:
        def __init__(self, values: list[object]):
            self.values = values

        def scalars(self):
            return self

        def all(self):
            return self.values

    class DB:
        def __init__(self):
            self.results = [
                Result([relation]),
                Result([
                    SimpleNamespace(name="title", target_subtype=None, parent_id=None, field_type="text"),
                    SimpleNamespace(name="publication_year", target_subtype=None, parent_id=None, field_type="text"),
                ]),
                Result([SimpleNamespace(
                    name="work", target_subtype=None, parent_id=None, field_type="relation",
                )]),
                Result([SimpleNamespace(
                    name="work", is_searchable=True, is_facet=False, is_public=True, field_type="relation",
                    settings={"target_type": "occurrence", "inherited_fields": ["publication_year"]},
                )]),
                Result([relation]),
                Result([SimpleNamespace(
                    name="publication_year", target_subtype=None, parent_id=None, field_type="text",
                )]),
            ]

        async def execute(self, _statement):
            return self.results.pop(0)

        async def get(self, _model, _record_id):
            return occurrence

    doc = await build_index_doc("object", obj, DB())

    assert doc["linked_occurrences"] == [{
        "id": str(occurrence_id), "relation_type": "is_edition_of",
        "inherited": {"publication_year": "1905"},
    }]
    assert doc["facet_inherited_occurrence_publication_year"] == ["1905"]


@pytest.mark.asyncio
async def test_index_doc_limits_inherited_fields_to_fixed_relation_type() -> None:
    object_id = uuid.uuid4()
    occurrence_id = uuid.uuid4()
    obj = Object(
        id=object_id, idno="OBJ-1", status="public", collection_status="active", metadata_={}
    )
    occurrence = Occurrence(
        id=occurrence_id,
        idno="OCC-1",
        occurrence_type="work",
        status="public",
        metadata_={"publication_year": "1905"},
    )
    relation = Relation(
        id=uuid.uuid4(),
        from_type="object",
        from_id=object_id,
        to_type="occurrence",
        to_id=occurrence_id,
        relation_type="is_author",
    )

    class Result:
        def __init__(self, values: list[object]):
            self.values = values

        def scalars(self):
            return self

        def all(self):
            return self.values

    class DB:
        def __init__(self):
            self.results = [
                Result([relation]),
                Result([
                    SimpleNamespace(name="publication_year", target_subtype=None, parent_id=None, field_type="text"),
                ]),
                Result([SimpleNamespace(
                    name="author", target_subtype=None, parent_id=None, field_type="relation",
                )]),
                Result([
                    SimpleNamespace(
                        name="author", is_public=True,
                        is_searchable=True,
                        is_facet=False,
                        field_type="relation",
                        settings={
                            "target_type": "occurrence",
                            "fixed_relation_type": "has_author",
                            "inherited_fields": ["publication_year"],
                        },
                    )
                ]),
                Result([relation]),
                Result([SimpleNamespace(
                    name="publication_year", target_subtype=None, parent_id=None, field_type="text",
                )]),
            ]

        async def execute(self, _statement):
            return self.results.pop(0)

        async def get(self, _model, _record_id):
            return occurrence

    doc = await build_index_doc("object", obj, DB())

    assert "linked_occurrences" not in doc
    assert "facet_inherited_occurrence_publication_year" not in doc


@pytest.mark.asyncio
async def test_reindex_type_accepts_procedure(monkeypatch) -> None:
    calls: list[str] = []

    class _FakeAsyncResult:
        id = "fake-task-id"

    def fake_delay(target_type: str) -> _FakeAsyncResult:
        calls.append(target_type)
        return _FakeAsyncResult()

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


@pytest.mark.asyncio
async def test_search_documents_allows_leading_wildcards(monkeypatch) -> None:
    captured: dict = {}

    class FakeES:
        async def search(self, **kwargs):
            captured.update(kwargs)
            return type("Result", (), {"body": {"hits": {"total": {"value": 0}, "hits": []}, "aggregations": {}}})()

    monkeypatch.setattr(elasticsearch, "get_es", lambda: FakeES())

    await elasticsearch.search_documents("*fragment", None, "public", 0, 20)

    query = captured["body"]["query"]["bool"]["must"][0]["query_string"]
    assert query["query"] == "*fragment"
    assert query["allow_leading_wildcard"] is True


@pytest.mark.asyncio
async def test_search_documents_filters_and_aggregates_inherited_facets(monkeypatch) -> None:
    captured: dict = {}

    class FakeES:
        async def search(self, **kwargs):
            captured.update(kwargs)
            return type("Result", (), {"body": {"hits": {"total": {"value": 0}, "hits": []}, "aggregations": {}}})()

    monkeypatch.setattr(elasticsearch, "get_es", lambda: FakeES())
    field = "inherited_occurrence_publication_year"

    await elasticsearch.search_documents(
        None, "object", "public", 0, 20,
        extra_filters={field: ["1905", "1906"]}, facet_fields=[field],
    )

    body = captured["body"]
    selected_values = {"terms": {f"facet_{field}": ["1905", "1906"]}}
    assert selected_values in body["query"]["bool"]["filter"]

    aggregation = body["aggs"][f"meta_{field}"]
    assert aggregation["global"] == {}
    assert selected_values not in aggregation["aggs"]["filtered"]["filter"]["bool"]["filter"]
    assert aggregation["aggs"]["filtered"]["aggs"]["values"] == {
        "terms": {"field": f"facet_{field}", "size": 20}
    }


@pytest.mark.asyncio
async def test_search_reads_self_excluding_facet_buckets(monkeypatch) -> None:
    async def search_documents(*args, **kwargs):
        return {
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {
                "meta_event_date": {
                    "doc_count": 21,
                    "filtered": {
                        "doc_count": 21,
                        "values": {
                            "buckets": [{"key": "Neolithikum", "doc_count": 17}]
                        },
                    },
                }
            },
        }

    monkeypatch.setattr(search_service, "search_documents", search_documents)

    result = await search_service.search(facet_fields=["event_date"])

    assert result["facets"]["meta_event_date"] == [
        {"value": "Neolithikum", "count": 17}
    ]
