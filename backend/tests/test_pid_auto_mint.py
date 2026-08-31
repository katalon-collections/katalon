from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.services.pid_service import PidMintError


def make_record(status: str = "draft") -> MagicMock:
    rec = MagicMock()
    rec.id = uuid.uuid4()
    rec.status = status
    rec.idno = "OBJ-1"
    rec.metadata_ = {}
    rec.object_type = None
    rec.version = 1
    return rec


@pytest.mark.asyncio
async def test_publish_mints_missing_pids(monkeypatch: pytest.MonkeyPatch) -> None:
    from katalon.services import publish_service

    record = make_record()
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = record
    db.execute = AsyncMock(return_value=result_mock)
    monkeypatch.setattr(publish_service, "can_publish", AsyncMock(return_value=(True, [])))
    monkeypatch.setattr(publish_service, "index_record", AsyncMock())

    ensure = AsyncMock(return_value=[])
    monkeypatch.setattr(publish_service, "ensure_pids_on_publish", ensure)

    result = await publish_service.publish_record(db, "object", str(record.id), str(uuid.uuid4()))
    assert result["ok"] is True
    ensure.assert_awaited_once()
    assert ensure.await_args.args[1] == "object"
    assert ensure.await_args.args[2] is record


@pytest.mark.asyncio
async def test_publish_blocked_when_mint_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from katalon.services import publish_service

    record = make_record()
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = record
    db.execute = AsyncMock(return_value=result_mock)
    monkeypatch.setattr(publish_service, "can_publish", AsyncMock(return_value=(True, [])))
    monkeypatch.setattr(publish_service, "index_record", AsyncMock())

    async def failing_ensure(*args, **kwargs):
        raise PidMintError("DNB-API nicht erreichbar")

    monkeypatch.setattr(publish_service, "ensure_pids_on_publish", failing_ensure)

    result = await publish_service.publish_record(db, "object", str(record.id), str(uuid.uuid4()))
    assert result["ok"] is False
    assert any("DNB-API nicht erreichbar" in e for e in result["errors"])
    # Status must stay untouched when minting fails.
    assert record.status == "draft"


@pytest.mark.asyncio
async def test_batch_set_status_public_triggers_auto_mint(monkeypatch: pytest.MonkeyPatch) -> None:
    from katalon.services import batch_service

    record = make_record(status="draft")
    ensure = AsyncMock(return_value=[])

    monkeypatch.setattr(batch_service, "ensure_pids_on_publish", ensure)
    monkeypatch.setattr(batch_service, "diff_fields", lambda old, new: {})
    monkeypatch.setattr(batch_service, "log_change", AsyncMock())

    changed = await batch_service._apply_status_change(
        AsyncMock(), record, "object", "public", None, uuid.uuid4()
    )
    assert changed is True
    ensure.assert_awaited_once()
    assert record.status == "public"


@pytest.mark.asyncio
async def test_batch_set_status_public_without_transition_skips_mint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from katalon.services import batch_service

    record = make_record(status="public")
    ensure = AsyncMock(return_value=[])

    monkeypatch.setattr(batch_service, "ensure_pids_on_publish", ensure)
    monkeypatch.setattr(batch_service, "diff_fields", lambda old, new: {})
    monkeypatch.setattr(batch_service, "log_change", AsyncMock())

    await batch_service._apply_status_change(
        AsyncMock(), record, "object", "public", None, uuid.uuid4()
    )
    ensure.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_set_status_non_public_skips_mint(monkeypatch: pytest.MonkeyPatch) -> None:
    from katalon.services import batch_service

    record = make_record(status="draft")
    ensure = AsyncMock(return_value=[])

    monkeypatch.setattr(batch_service, "ensure_pids_on_publish", ensure)
    monkeypatch.setattr(batch_service, "diff_fields", lambda old, new: {})
    monkeypatch.setattr(batch_service, "log_change", AsyncMock())

    await batch_service._apply_status_change(
        AsyncMock(), record, "object", "internal", None, uuid.uuid4()
    )
    ensure.assert_not_awaited()
