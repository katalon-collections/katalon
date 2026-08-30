import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from katalon.api.v1 import index_health
from katalon.api.v1.search import trigger_reindex_type
from katalon.core.models import Object, Occurrence, Procedure, Relation
from katalon.integrations import elasticsearch
from katalon.services import search_service
from katalon.services.search_service import build_index_doc, date_bounds


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


def test_date_bounds_cover_partial_and_open_edtf_dates() -> None:
    assert date_bounds("1950") == (19500101, 19501231)
    assert date_bounds("1950-02") == (19500201, 19500228)
    assert date_bounds("1900~/1950?") == (19000101, 19501231)
    assert date_bounds("/1950") == (None, 19501231)


@pytest.mark.parametrize("value", ["1950-13", "1950-02-30", "1951/1950"])
def test_date_bounds_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        date_bounds(value)


def test_index_doc_builds_typed_advanced_fields_and_relation_ids() -> None:
    obj = Object(
        id=uuid.uuid4(), idno="OBJ-1", status="public", collection_status="active",
        metadata_={
            "title": "Ansicht von Bremen",
            "year": 1949,
            "material": {"id": "term-1", "label": "Stein"},
            "photographer": {
                "id": str(uuid.uuid4()), "label": "Ada Beispiel", "relation_type": "created_by",
            },
        },
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 2),
    )
    fields = [
        SimpleNamespace(
            name="title", field_type="text", is_searchable=True, is_public=True,
            is_facet=False, settings={},
        ),
        SimpleNamespace(
            name="year", field_type="number", is_searchable=True, is_public=True,
            is_facet=False, settings={},
        ),
        SimpleNamespace(
            name="material", field_type="vocab", is_searchable=True, is_public=True,
            is_facet=False, settings={},
        ),
        SimpleNamespace(
            name="photographer", field_type="relation", is_searchable=True, is_public=True,
            is_facet=False, settings={"target_type": "entity"},
        ),
    ]

    doc = search_service._build_doc(
        "object", obj, searchable_fields={"title", "year", "photographer"},
        field_definitions=fields,
    )

    assert {"name": "title", "text_value": "Ansicht von Bremen", "keyword_value": "Ansicht von Bremen"} in doc["adv_fields"]
    assert {"name": "year", "number_value": 1949.0} in doc["adv_fields"]
    assert {"name": "material", "text_value": "Stein", "keyword_value": "Stein"} in doc["adv_fields"]
    assert {"name": "material", "text_value": "term-1", "keyword_value": "term-1"} in doc["adv_fields"]
    assert doc["adv_relations"] == [{
        "source_field": "photographer",
        "target_type": "entity",
        "target_id": obj.metadata_["photographer"]["id"],
        "relation_type": "created_by",
    }]


def test_index_doc_builds_numeric_facet_field() -> None:
    obj = Object(
        id=uuid.uuid4(), idno="OBJ-1", status="public", collection_status="active",
        metadata_={"year": [{"value": "1949"}, {"value": "1950"}]},
    )
    fields = [SimpleNamespace(
        name="year", field_type="number", is_searchable=False, is_public=True,
        is_facet=True, settings={},
    )]

    doc = search_service._build_doc(
        "object", obj, facet_fields={"year"}, field_definitions=fields,
    )

    assert doc["facet_year"] == ["1949", "1950"]
    assert doc["number_facet_year"] == [1949.0, 1950.0]


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
async def test_intermediate_search_tracks_exact_total(monkeypatch) -> None:
    captured: dict = {}

    class FakeES:
        async def search(self, **kwargs):
            captured.update(kwargs)
            return type("Result", (), {"body": {"hits": {"total": {"value": 10001}, "hits": []}}})()

    monkeypatch.setattr(elasticsearch, "get_es", lambda: FakeES())

    _, truncated = await elasticsearch.search_ids_by_filter("entity", {"match_all": {}}, limit=10000)

    assert captured["body"]["track_total_hits"] is True
    assert truncated is True


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
async def test_search_documents_filters_and_aggregates_numeric_facets(monkeypatch) -> None:
    captured: dict = {}

    class FakeES:
        async def search(self, **kwargs):
            captured.update(kwargs)
            return type("Result", (), {"body": {"hits": {"total": {"value": 0}, "hits": []}, "aggregations": {}}})()

    monkeypatch.setattr(elasticsearch, "get_es", lambda: FakeES())
    await elasticsearch.search_documents(
        None, "object", "public", 0, 20,
        numeric_filters={"year": (1900.0, 1950.0)}, facet_fields=["year"],
    )

    body = captured["body"]
    selected_range = {"range": {"number_facet_year": {"gte": 1900.0, "lte": 1950.0}}}
    assert selected_range in body["query"]["bool"]["filter"]
    aggregation = body["aggs"]["numeric_year"]
    assert selected_range not in aggregation["aggs"]["filtered"]["filter"]["bool"]["filter"]
    assert aggregation["aggs"]["filtered"]["aggs"]["values"] == {
        "stats": {"field": "number_facet_year"}
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
