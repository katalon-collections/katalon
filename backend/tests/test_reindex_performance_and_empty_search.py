# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Regression tests for empty-index search safety and reindex CLI."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from elasticsearch import NotFoundError

from katalon.integrations import elasticsearch
from katalon.management.cli import cli


def test_index_mapping_defines_idno_keyword_subfield() -> None:
    """An empty freshly initialized index must already have the idno.keyword mapping
    so default idno_asc sorting never triggers a BadRequestError."""
    props = elasticsearch.INDEX_SETTINGS["mappings"]["properties"]
    assert "idno" in props
    assert props["idno"]["fields"]["keyword"]["type"] == "keyword"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sort_param", "expected_field", "expected_order", "expected_unmapped"),
    [
        (None, "idno.keyword", "asc", "keyword"),
        ("idno_asc", "idno.keyword", "asc", "keyword"),
        ("title_asc", "title.raw", "asc", "keyword"),
        ("newest", "created_at", "desc", "date"),
        ("oldest", "created_at", "asc", "date"),
    ],
)
async def test_search_documents_sort_clauses_set_unmapped_type(
    monkeypatch: pytest.MonkeyPatch,
    sort_param: str | None,
    expected_field: str,
    expected_order: str,
    expected_unmapped: str,
) -> None:
    """Every deterministic sort clause sets unmapped_type so sorting on an empty or
    legacy unmapped index returns 0 hits instead of HTTP 422."""
    captured: dict[str, Any] = {}

    class FakeES:
        async def search(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return type(
                "Result",
                (),
                {"body": {"hits": {"total": {"value": 0}, "hits": []}, "aggregations": {}}},
            )()

    monkeypatch.setattr(elasticsearch, "get_es", lambda: FakeES())

    await elasticsearch.search_documents(None, "object", "public", 0, 20, sort=sort_param)

    assert captured["body"]["sort"] == [
        {expected_field: {"order": expected_order, "unmapped_type": expected_unmapped}}
    ]


def test_reverse_sort_preserves_unmapped_type() -> None:
    clauses = [{"idno.keyword": {"order": "asc", "unmapped_type": "keyword"}}]
    assert elasticsearch._reverse_sort(clauses) == [
        {"idno.keyword": {"order": "desc", "unmapped_type": "keyword"}}
    ]
    assert elasticsearch._reverse_sort([{"created_at": "desc"}]) == [{"created_at": "asc"}]


@pytest.mark.asyncio
async def test_search_documents_returns_empty_when_index_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before the index exists (e.g. fresh ES right after restore), search returns
    an empty hit set instead of raising NotFoundError."""

    class MissingIndexES:
        async def search(self, **kwargs: Any) -> Any:
            raise NotFoundError("index_not_found_exception", MagicMock(), {})

    monkeypatch.setattr(elasticsearch, "get_es", lambda: MissingIndexES())

    result = await elasticsearch.search_documents(None, "object", "public", 0, 20)

    assert result["hits"]["total"]["value"] == 0
    assert result["hits"]["hits"] == []


def test_cli_reindex_enqueues_full_and_typed_and_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from katalon.workers import index_tasks, reindex_state

    full_calls: list[bool] = []
    type_calls: list[str] = []
    sync_calls: list[str] = []

    monkeypatch.setattr(
        reindex_state,
        "request_full_rebuild",
        lambda *, strict=False: (full_calls.append(strict) or True),
    )
    monkeypatch.setattr(
        reindex_state,
        "request_bulk_reindex",
        lambda target_type, *, strict=False: (type_calls.append(target_type) or True),
    )
    monkeypatch.setattr(
        reindex_state,
        "read_status",
        lambda types: {
            "__all__": {"progress": {"state": "running", "built": "2", "total": "7"}, "queued": False, "dirty": True, "locked": True},
            "object": {"progress": {"state": "running", "built": "500", "total": "1000"}, "queued": False, "dirty": False, "locked": True},
        },
    )
    monkeypatch.setattr(
        index_tasks.bulk_reindex_type_task,
        "run",
        lambda target_type: (sync_calls.append(target_type) or {"status": "ok", "indexed": 12, "removed": 0}),
    )

    runner = CliRunner()

    res_full = runner.invoke(cli, ["reindex"])
    assert res_full.exit_code == 0, res_full.output
    assert full_calls == [False]

    res_type = runner.invoke(cli, ["reindex", "--type", "object"])
    assert res_type.exit_code == 0, res_type.output
    assert type_calls == ["object"]

    res_sync = runner.invoke(cli, ["reindex", "--type", "object", "--sync"])
    assert res_sync.exit_code == 0, res_sync.output
    assert sync_calls == ["object"]
    assert "12" in res_sync.output

    res_status = runner.invoke(cli, ["reindex", "--status"])
    assert res_status.exit_code == 0, res_status.output
    assert "object" in res_status.output
    assert "500/1000" in res_status.output
