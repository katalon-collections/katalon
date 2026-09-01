# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from types import SimpleNamespace

import pytest

from katalon.services import advanced_search_service
from katalon.services.advanced_search_service import (
    AdvancedFieldClause,
    AdvancedGroup,
    AdvancedQuery,
    AdvancedRelationClause,
)


class _Result:
    def __init__(self, values: list[object]):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _DB:
    def __init__(self, fields_by_type: dict[str, list[object]]):
        self.fields_by_type = fields_by_type

    async def execute(self, statement):
        record_type = statement.compile().params.get("target_type_1")
        return _Result(self.fields_by_type.get(record_type, []))


@pytest.mark.asyncio
async def test_text_contains_matches_case_insensitive_substrings() -> None:
    fields = {
        "object": [SimpleNamespace(
            name="label", field_type="text", is_public=True,
            is_searchable=True, parent_id=None, settings={},
        )]
    }
    query = AdvancedQuery(
        record_type="object",
        group=AdvancedGroup(clauses=[
            AdvancedFieldClause(field="label", operator="contains", value="beil")
        ]),
    )

    resolved = await advanced_search_service.resolve_query(_DB(fields), query)

    value_filter = resolved["bool"]["filter"][0]["nested"]["query"]["bool"]["filter"][1]
    assert value_filter == {
        "wildcard": {
            "adv_fields.keyword_value": {"value": "*beil*", "case_insensitive": True}
        }
    }


@pytest.mark.asyncio
async def test_direct_field_types_compile_to_typed_index_values() -> None:
    def field(name: str, field_type: str):
        return SimpleNamespace(
            name=name, field_type=field_type, is_public=True,
            is_searchable=True, parent_id=None, settings={},
        )

    fields = {"object": [
        field("year", "number"), field("available", "boolean"),
        field("subject", "vocab"), field("authority", "authority"),
        field("pid", "pid"),
    ]}
    query = AdvancedQuery(
        record_type="object",
        group=AdvancedGroup(clauses=[
            AdvancedFieldClause(field="year", operator="between", value=[1900, 1950]),
            AdvancedFieldClause(field="available", operator="eq", value=True),
            AdvancedFieldClause(field="subject", operator="eq", value="term-id"),
            AdvancedFieldClause(field="authority", operator="eq", value="Ada Lovelace"),
            AdvancedFieldClause(field="pid", operator="eq", value="doi:example"),
        ]),
    )

    resolved = await advanced_search_service.resolve_query(_DB(fields), query)

    assert len(resolved["bool"]["filter"]) == 5


@pytest.mark.asyncio
async def test_resolve_two_hop_relation_query_from_inside_out(monkeypatch) -> None:
    fields = {
        "object": [
            SimpleNamespace(
                name="photographer", field_type="relation", is_public=True,
                is_searchable=True, parent_id=None, settings={"target_type": "entity"},
            )
        ],
        "entity": [
            SimpleNamespace(
                name="birth_date", field_type="date", is_public=True,
                is_searchable=True, parent_id=None, settings={},
            ),
            SimpleNamespace(
                name="birth_place", field_type="relation", is_public=True,
                is_searchable=True, parent_id=None, settings={"target_type": "place"},
            ),
        ],
        "place": [
            SimpleNamespace(
                name="name", field_type="text", is_public=True,
                is_searchable=True, parent_id=None, settings={},
            )
        ],
    }
    calls: list[tuple[str, dict]] = []

    async def fake_search_ids(record_type: str, advanced_filter: dict, *, limit: int):
        calls.append((record_type, advanced_filter))
        return (["place-1"] if record_type == "place" else ["entity-1"], False)

    monkeypatch.setattr(advanced_search_service, "search_ids_by_filter", fake_search_ids)
    query = AdvancedQuery(
        record_type="object",
        group=AdvancedGroup(
            mode="all",
            clauses=[
                AdvancedRelationClause(
                    field="photographer",
                    group=AdvancedGroup(
                        mode="all",
                        clauses=[
                            AdvancedFieldClause(field="birth_date", operator="before", value="1950"),
                            AdvancedRelationClause(
                                field="birth_place",
                                group=AdvancedGroup(
                                    mode="all",
                                    clauses=[
                                        AdvancedFieldClause(field="name", operator="eq", value="Bremen")
                                    ],
                                ),
                            ),
                        ],
                    ),
                )
            ],
        ),
    )

    resolved = await advanced_search_service.resolve_query(_DB(fields), query)

    assert [record_type for record_type, _ in calls] == ["place", "entity"]
    assert resolved == {"bool": {"filter": [{
        "nested": {
            "path": "adv_relations",
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"adv_relations.source_field": "photographer"}},
                        {"terms": {"adv_relations.target_id": ["entity-1"]}},
                    ]
                }
            },
        }
    }]}}


@pytest.mark.asyncio
async def test_resolve_query_rejects_third_relation_hop(monkeypatch) -> None:
    def relation(name, target):
        return SimpleNamespace(
            name=name, field_type="relation", is_public=True, is_searchable=True,
            parent_id=None, settings={"target_type": target},
        )
    fields = {
        "object": [relation("photographer", "entity")],
        "entity": [relation("birth_place", "place")],
        "place": [relation("region", "place")],
    }
    monkeypatch.setattr(
        advanced_search_service,
        "search_ids_by_filter",
        lambda *args, **kwargs: (["id"], False),
    )
    query = AdvancedQuery(
        record_type="object",
        group=AdvancedGroup(
            clauses=[AdvancedRelationClause(
                field="photographer",
                group=AdvancedGroup(clauses=[AdvancedRelationClause(
                    field="birth_place",
                    group=AdvancedGroup(clauses=[AdvancedRelationClause(
                        field="region",
                        group=AdvancedGroup(clauses=[
                            AdvancedFieldClause(field="name", operator="eq", value="Bremen")
                        ]),
                    )]),
                )]),
            )],
        ),
    )

    with pytest.raises(ValueError, match="höchstens zwei Relationsschritte"):
        await advanced_search_service.resolve_query(_DB(fields), query)
