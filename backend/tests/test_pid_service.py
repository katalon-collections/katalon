from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.services.pid_service import (
    DEFAULT_PID_PROVIDER,
    PID_PROVIDERS,
    PidMintError,
    _is_empty_pid_value,
    _provider_for_field,
    ensure_pids_on_publish,
    mint_pid_for_record,
    record_portal_url,
)


def make_pid_field(
    name: str = "pid",
    *,
    provider: str | None = "ark",
    is_repeatable: bool = False,
) -> MagicMock:
    f = MagicMock()
    f.name = name
    f.field_type = "pid"
    f.is_repeatable = is_repeatable
    f.settings = {"pid_provider": provider} if provider else {}
    f.id = uuid.uuid4()
    return f


def make_record(status: str = "public", metadata: dict | None = None) -> MagicMock:
    rec = MagicMock()
    rec.id = uuid.uuid4()
    rec.status = status
    rec.metadata_ = metadata or {}
    rec.object_type = None
    return rec


def mock_db(*fields: MagicMock) -> AsyncMock:
    """Mock DB whose first execute returns the given field definitions."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(fields)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_mints_ark_for_empty_pid_field(monkeypatch: pytest.MonkeyPatch) -> None:
    field = make_pid_field("pid", provider="ark")
    record = make_record(metadata={})
    db = mock_db(field)

    minted: list[dict] = []

    async def fake_mint(**kwargs):
        minted.append(kwargs)
        return {
            "pid": "ark:/99999/abc",
            "resolver_url": "https://n2t.net/ark:/99999/abc",
            "value": {"value": "ark:/99999/abc", "label": "ARK"},
            "metadata": {"pid": {"value": "ark:/99999/abc", "label": "ARK"}},
            "provider": "ark",
        }

    import katalon.services.pid_service as svc
    from katalon.services import schema_service

    # ensure_pids_on_publish resolves these lazily inside the function body.
    monkeypatch.setattr(schema_service, "get_field_definitions", AsyncMock(return_value=[field]))
    monkeypatch.setattr("katalon.services.audit_service.log_change", AsyncMock())
    monkeypatch.setattr(svc, "mint_pid_for_record", fake_mint)

    mint_results = await ensure_pids_on_publish(db, "object", record)
    assert len(mint_results) == 1
    assert minted[0]["field_name"] == "pid"


@pytest.mark.asyncio
async def test_skips_filled_pid_field(monkeypatch: pytest.MonkeyPatch) -> None:
    field = make_pid_field("pid", provider="ark")
    record = make_record(metadata={"pid": {"value": "ark:/99999/xyz", "label": "ARK"}})

    import katalon.services.pid_service as svc
    from katalon.services import schema_service

    called = False

    async def fake_mint(**kwargs):
        nonlocal called
        called = True
        return {}

    async def fake_get_fields(db, record_type, target_subtype=None):
        return [field]

    monkeypatch.setattr(svc, "mint_pid_for_record", fake_mint)
    monkeypatch.setattr(schema_service, "get_field_definitions", fake_get_fields)

    mint_results = await ensure_pids_on_publish(AsyncMock(), "object", record)
    assert mint_results == []
    assert called is False


@pytest.mark.asyncio
async def test_skips_field_without_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    field = make_pid_field("pid", provider=None)
    record = make_record(metadata={})

    import katalon.services.pid_service as svc
    from katalon.services import schema_service

    called = False

    async def fake_mint(**kwargs):
        nonlocal called
        called = True
        return {}

    async def fake_get_fields(db, record_type, target_subtype=None):
        return [field]

    monkeypatch.setattr(svc, "mint_pid_for_record", fake_mint)
    monkeypatch.setattr(schema_service, "get_field_definitions", fake_get_fields)

    mint_results = await ensure_pids_on_publish(AsyncMock(), "object", record)
    assert mint_results == []
    assert called is False


@pytest.mark.asyncio
async def test_mint_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    field = make_pid_field("pid", provider="dnb_urn")
    record = make_record(metadata={})

    import katalon.services.pid_service as svc
    from katalon.services import schema_service

    async def fake_mint(**kwargs):
        raise PidMintError("DNB down")

    async def fake_get_fields(db, record_type, target_subtype=None):
        return [field]

    monkeypatch.setattr(svc, "mint_pid_for_record", fake_mint)
    monkeypatch.setattr(schema_service, "get_field_definitions", fake_get_fields)

    with pytest.raises(PidMintError, match="DNB down"):
        await ensure_pids_on_publish(AsyncMock(), "object", record)


@pytest.mark.asyncio
async def test_mint_does_not_replace_reserved_pid() -> None:
    record = make_record(metadata={"pid": {"value": "ark:/99999/abc", "label": "ARK"}})
    field = make_pid_field()
    record_result = MagicMock()
    record_result.scalar_one_or_none.return_value = record
    field_result = MagicMock()
    field_result.scalar_one_or_none.return_value = field
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[record_result, field_result])

    with pytest.raises(ValueError, match="bereits reserviert"):
        await mint_pid_for_record(db, "object", record.id, "pid")


def test_provider_for_field() -> None:
    assert _provider_for_field(make_pid_field(provider="ark")) == "ark"
    assert _provider_for_field(make_pid_field(provider=None)) == DEFAULT_PID_PROVIDER
    assert "ark" in PID_PROVIDERS and "dnb_urn" in PID_PROVIDERS
    with pytest.raises(PidMintError, match="unbekannter PID-Provider"):
        _provider_for_field(make_pid_field(provider="doi"))


def test_record_portal_url_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch through the module-local settings reference that record_portal_url
    # actually reads — integration tests reload katalon.config, which swaps the
    # katalon.config.settings object without rebinding already-imported modules.
    import katalon.services.pid_service as svc

    monkeypatch.setattr(svc.settings, "katalon_base_url", "")
    with pytest.raises(PidMintError, match="KATALON_BASE_URL"):
        record_portal_url("object", uuid.uuid4())

    monkeypatch.setattr(svc.settings, "katalon_base_url", "https://katalon.example/")
    url = record_portal_url("entity", uuid.UUID(int=1))
    assert url == "https://katalon.example/entities/00000000-0000-0000-0000-000000000001"


def test_is_empty_pid_value() -> None:
    assert _is_empty_pid_value(None)
    assert _is_empty_pid_value("")
    assert _is_empty_pid_value([])
    assert not _is_empty_pid_value({"value": "ark:/99999/a"})
    assert not _is_empty_pid_value([{"value": "urn:x"}])
