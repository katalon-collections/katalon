# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Regression tests for ARK resolution, 410 tombstones, SEO 410, and portal tombstone config."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.api.v1 import ark as ark_api
from katalon.core.dependencies import get_db, try_get_current_user
from katalon.core.models import Collection, Object, PortalConfig, User
from katalon.core.visibility import ensure_publicly_visible
from katalon.main import app
from katalon.services import ark_service


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.mark.asyncio
async def test_resolve_ark_includes_soft_deleted_public_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ARK lookup must not exclude soft-deleted public records so callers reach the 410 tombstone."""
    record_id = uuid.uuid4()
    executed_sql: list[str] = []
    session = AsyncMock()

    async def execute(statement, params=None):
        executed_sql.append(str(statement))
        return _scalar_result(record_id if len(executed_sql) == 1 else None)

    session.execute.side_effect = execute
    monkeypatch.setattr("katalon.services.pid_service.settings.katalon_base_url", "https://catalog.example.org")

    target = await ark_service.resolve_ark(session, "ark:/12345/withdrawn1")

    assert target == f"https://catalog.example.org/objects/{record_id}"
    assert "deleted_at IS NULL" not in executed_sql[0]
    assert "status = ANY(:statuses)" in executed_sql[0]


@pytest.mark.asyncio
async def test_ark_endpoint_redirects_soft_deleted_public_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_id = uuid.uuid4()
    session = AsyncMock()
    session.execute.return_value = _scalar_result(record_id)
    monkeypatch.setattr(ark_api.settings, "ark_naan", "12345")
    monkeypatch.setattr(ark_api.settings, "ark_enabled", False)
    monkeypatch.setattr("katalon.services.pid_service.settings.katalon_base_url", "https://catalog.example.org")

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/ark:/12345/withdrawn1", follow_redirects=False)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 303
    assert response.headers["location"] == f"https://catalog.example.org/objects/{record_id}"


def test_ensure_publicly_visible_never_leaks_deleted_draft_as_410() -> None:
    """A soft-deleted record that was never public must return 404, not 410."""
    draft = Object(
        id=uuid.uuid4(),
        idno="DRAFT-1",
        status="draft",
        metadata_={},
        deleted_at=datetime.now(UTC).replace(tzinfo=None),
    )
    with pytest.raises(Exception) as exc_info:
        ensure_publicly_visible(draft, None, "Objekt nicht gefunden")
    assert exc_info.value.status_code == 404  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_portal_object_returns_410_for_signed_in_staff_on_deleted_public_record() -> None:
    """In the portal, both anonymous visitors and signed-in staff see 410 for withdrawn public records."""
    obj = Object(
        id=uuid.uuid4(),
        idno="OBJ-GONE",
        status="public",
        collection_status="active",
        metadata_={"label": "Withdrawn object"},
        ai_provenance={},
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
        deleted_at=datetime.now(UTC).replace(tzinfo=None),
        version=1,
    )
    staff = User(id=uuid.uuid4(), email="admin@example.org", hashed_password="x", role="admin")
    session = AsyncMock()
    session.execute.return_value = _scalar_result(obj)

    async def override_db():
        yield session

    async def override_user():
        return staff

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[try_get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/objects/{obj.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)

    assert response.status_code == 410


@pytest.mark.asyncio
async def test_portal_collection_returns_410_for_deleted_public_collection() -> None:
    col = Collection(
        id=uuid.uuid4(),
        idno="COL-GONE",
        status="public",
        metadata_={"title": "Withdrawn collection"},
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
        deleted_at=datetime.now(UTC).replace(tzinfo=None),
        version=1,
    )
    session = AsyncMock()
    session.execute.return_value = _scalar_result(col)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/collections/{col.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 410


@pytest.mark.asyncio
async def test_seo_page_returns_410_html_for_deleted_public_record() -> None:
    obj = Object(
        id=uuid.uuid4(),
        idno="OBJ-GONE",
        status="public",
        collection_status="active",
        metadata_={"label": "Withdrawn object"},
        ai_provenance={},
        created_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
        deleted_at=datetime.now(UTC).replace(tzinfo=None),
        version=1,
    )
    config = PortalConfig(
        key="default",
        site_title={"de": "Sammlung"},
    )
    session = AsyncMock()
    session.execute.side_effect = [_scalar_result(obj), _scalar_result(config)]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/seo/objects/{obj.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 410
    assert "text/html" in response.headers["content-type"]
    assert '<meta name="robots" content="noindex">' in response.text
    assert "Datensatz zurückgezogen" in response.text
