import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.api.v1.auth import hash_password, verify_password
from katalon.core.dependencies import get_current_user
from katalon.core.models import AuditLog, User
from katalon.database import get_db
from katalon.main import app


def _mock_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.fixture
def override_deps():
    session = AsyncMock()
    session.add = MagicMock()

    user = User(
        id=uuid.uuid4(),
        email="admin@example.org",
        hashed_password=hash_password("Current123"),
        role="admin",
        is_active=True,
        created_at=datetime.now(),
    )

    async def override_db():
        yield session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    yield session, user
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_change_own_password_writes_audit_log(override_deps) -> None:
    session, user = override_deps
    old_hash = user.hashed_password
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/v1/users/me/password", json={
            "current_password": "Current123",
            "new_password": "NewPass123",
        })

    assert response.status_code == 204
    assert user.hashed_password != old_hash
    assert verify_password("NewPass123", user.hashed_password)
    audit_entries = [
        call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], AuditLog)
    ]
    assert len(audit_entries) == 1
    assert audit_entries[0].changed_fields == {"password": "updated"}


@pytest.mark.asyncio
async def test_set_own_onboarding_completed(override_deps) -> None:
    _, user = override_deps
    assert user.onboarding_completed_at is None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/v1/users/me/onboarding", json={"completed": True})

    assert response.status_code == 200
    assert response.json()["onboarding_completed_at"] is not None
    assert user.onboarding_completed_at is not None


@pytest.mark.asyncio
async def test_reset_own_onboarding(override_deps) -> None:
    _, user = override_deps
    user.onboarding_completed_at = datetime.now()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/v1/users/me/onboarding", json={"completed": False})

    assert response.status_code == 200
    assert response.json()["onboarding_completed_at"] is None
    assert user.onboarding_completed_at is None


@pytest.mark.asyncio
async def test_change_own_email_requires_current_password(override_deps) -> None:
    session, _ = override_deps
    session.execute = AsyncMock(return_value=_mock_result(None))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/v1/users/me/email", json={
            "new_email": "new@example.org",
            "current_password": "WrongPass123",
        })

    assert response.status_code == 400
    assert response.json()["detail"] == "Aktuelles Passwort falsch"


@pytest.mark.asyncio
async def test_admin_update_user_email_password_writes_audit_log(override_deps) -> None:
    session, admin_user = override_deps
    target_user = User(
        id=uuid.uuid4(),
        email="cataloger@example.org",
        hashed_password=hash_password("Initial123"),
        role="cataloger",
        is_active=True,
        created_at=datetime.now(),
    )
    session.execute = AsyncMock(side_effect=[
        _mock_result(target_user),  # fetch target user
        _mock_result(None),  # email uniqueness check
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(f"/v1/users/{target_user.id}", json={
            "email": "updated@example.org",
            "password": "Updated123",
        })

    assert response.status_code == 200
    assert response.json()["email"] == "updated@example.org"
    audit_entries = [
        call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], AuditLog)
    ]
    assert len(audit_entries) == 1
    assert audit_entries[0].user_id == admin_user.id
    assert audit_entries[0].changed_fields["password"] == "updated"
    assert audit_entries[0].changed_fields["email"]["new"] == "updated@example.org"


@pytest.mark.asyncio
async def test_admin_can_change_user_role(override_deps) -> None:
    session, _ = override_deps
    target_user = User(
        id=uuid.uuid4(),
        email="cataloger@example.org",
        hashed_password=hash_password("Initial123"),
        role="cataloger",
        is_active=True,
        created_at=datetime.now(),
    )
    session.execute = AsyncMock(side_effect=[
        _mock_result(target_user),
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(f"/v1/users/{target_user.id}", json={"role": "editor"})

    assert response.status_code == 200
    assert target_user.role == "editor"


@pytest.mark.asyncio
async def test_self_deactivation_blocked(override_deps) -> None:
    session, user = override_deps
    session.execute = AsyncMock(side_effect=[
        _mock_result(user),
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(f"/v1/users/{user.id}", json={"is_active": False})

    assert response.status_code == 400
    assert "deaktiviert" in response.json()["detail"]
    assert user.is_active is True


@pytest.mark.asyncio
async def test_self_demotion_blocked(override_deps) -> None:
    session, user = override_deps
    session.execute = AsyncMock(side_effect=[
        _mock_result(user),
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(f"/v1/users/{user.id}", json={"role": "editor"})

    assert response.status_code == 400
    assert "Admin-Rolle" in response.json()["detail"]
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_self_delete_blocked(override_deps) -> None:
    session, user = override_deps
    session.execute = AsyncMock(side_effect=[
        _mock_result(user),
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/v1/users/{user.id}")

    assert response.status_code == 400
    assert "gelöscht" in response.json()["detail"]
