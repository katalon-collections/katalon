# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""OAI-PMH deleted records: tracking, paging (live records, then deletions), GetRecord."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from katalon.api.v1 import oai
from katalon.services import oai_state_service, oaipmh_service
from katalon.services.oai_state_service import DeletedRecord

OAI = "{http://www.openarchives.org/OAI/2.0/}"


def _hit(i: int) -> dict[str, Any]:
    return {"_id": f"live-{i}", "_source": {"record_type": "object", "updated_at": "2026-10-01T10:00:00"},
            "sort": [i]}


def _gone(i: int) -> DeletedRecord:
    return DeletedRecord("object", str(uuid.UUID(int=i)), datetime(2026, 10, 2, 8, 0, i))


# ---------------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_track_marks_public_and_withdrawn_records() -> None:
    db = AsyncMock()
    record = SimpleNamespace(id=uuid.uuid4(), status="public", deleted_at=None)
    await oai_state_service.track(db, "object", record)
    upsert = db.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    assert "ON CONFLICT" in str(upsert)

    record.status = "internal"
    await oai_state_service.track(db, "object", record)
    withdraw = str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert withdraw.startswith("UPDATE oai_record_states SET deleted_at")
    # Only rows of records that were public before are touched.
    assert "oai_record_states.deleted_at IS NULL" in withdraw


@pytest.mark.asyncio
async def test_internal_types_are_not_tracked() -> None:
    db = AsyncMock()
    await oai_state_service.mark_public(db, "storage_location", uuid.uuid4())
    await oai_state_service.mark_withdrawn(db, "procedure", uuid.uuid4())
    db.execute.assert_not_awaited()


@pytest.mark.parametrize(("value", "end", "expected"), [
    ("2026-10-02", False, datetime(2026, 10, 2)),
    ("2026-10-02", True, datetime(2026, 10, 2, 23, 59, 59, 999999)),
    ("2026-10-02T08:00:01Z", False, datetime(2026, 10, 2, 8, 0, 1)),
    ("kaputt", False, None),
])
def test_parse_oai_date(value: str, end: bool, expected: datetime | None) -> None:
    assert oai_state_service.parse_oai_date(value, end=end) == expected


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_identify_declares_transient_deletions() -> None:
    xml = oaipmh_service.identify("http://t/oai", "Repo", "a@b.c", "2024-01-01T00:00:00Z")
    assert "<deletedRecord>transient</deletedRecord>" in xml


def test_list_identifiers_renders_deleted_headers() -> None:
    xml = oaipmh_service.list_identifiers(
        [], 1, 0, None, None, None, "lido", "http://t/oai",
        deleted=[_gone(1)], resumption=oaipmh_service.Resumption(None, 1, 0),
    )
    header = ET.fromstring(xml).find(f".//{OAI}header")
    assert header is not None
    assert header.get("status") == "deleted"
    assert header.findtext(f"{OAI}datestamp") == "2026-10-02T08:00:01Z"


def test_token_carries_phase_and_total() -> None:
    token = oaipmh_service.encode_token(5, ["2026-10-02T08:00:01", "x"], None, None, None, "lido",
                                        phase="deleted", total=9)
    data = oaipmh_service.decode_token(token)
    assert (data["phase"], data["total"], data["offset"]) == ("deleted", 9, 5)
    # Old tokens (no phase) keep working.
    assert oaipmh_service.decode_token(oaipmh_service.encode_token(0, None, None, None, None, "x"))["phase"] == "records"


# ---------------------------------------------------------------------------
# Paging: live records first, then deletions
# ---------------------------------------------------------------------------


@pytest.fixture
def harvest(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    live = [_hit(i) for i in range(3)]
    gone = [_gone(i) for i in range(3)]
    monkeypatch.setattr(oai, "PAGE_SIZE", 2)

    async def es_search(_set: Any, _f: Any, _u: Any, search_after: Any, **_kw: Any) -> dict[str, Any]:
        start = 0 if not search_after else search_after[0] + 1
        return {"hits": {"hits": live[start:start + 2], "total": {"value": len(live)}}}

    async def deleted_page(_db: Any, _types: Any, _f: Any, _u: Any, after: Any, limit: int) -> list[DeletedRecord]:
        start = 0 if not after else next(i for i, g in enumerate(gone) if g.record_id == after[1]) + 1
        return gone[start:start + limit]

    monkeypatch.setattr(oai, "_es_search_for_oai", es_search)
    monkeypatch.setattr(oai_state_service, "count_deleted", AsyncMock(return_value=len(gone)))
    monkeypatch.setattr(oai_state_service, "deleted_page", deleted_page)
    return {"live": live, "gone": gone}


@pytest.mark.asyncio
async def test_harvest_pages_through_live_records_then_deletions(harvest: dict[str, Any]) -> None:
    seen_live: list[str] = []
    seen_gone: list[str] = []
    token: dict[str, Any] | None = None
    cursors: list[tuple[int, int]] = []
    for _ in range(10):
        hits, deleted, resumption = await oai._harvest_page(
            AsyncMock(), None, None, None, None, "lido", {"object"}, token
        )
        seen_live += [h["_id"] for h in hits]
        seen_gone += [d.record_id for d in deleted]
        cursors.append((resumption.cursor, resumption.complete_list_size))
        if resumption.token is None:
            break
        token = oaipmh_service.decode_token(resumption.token)
    assert seen_live == ["live-0", "live-1", "live-2"]
    assert seen_gone == [g.record_id for g in harvest["gone"]]
    assert all(size == 6 for _cursor, size in cursors)
    assert [cursor for cursor, _size in cursors] == [0, 2, 3, 5]


@pytest.mark.asyncio
async def test_metadata_sets_report_no_deletions(harvest: dict[str, Any]) -> None:
    set_def = SimpleNamespace(filter_metadata={"x": "y"}, filter_q=None, filter_status=None,
                              filter_record_type=None)
    assert oai._deletions_apply(set_def, {"object"}) == set()  # type: ignore[arg-type]
    type_set = SimpleNamespace(filter_metadata=None, filter_q=None, filter_status=None,
                               filter_record_type="entity")
    assert oai._deletions_apply(type_set, {"object", "entity"}) == {"entity"}  # type: ignore[arg-type]
