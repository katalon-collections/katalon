import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt

from katalon.api.v1.auth import create_access_token, hash_password, verify_password
from katalon.config import settings
from katalon.core.dependencies import get_current_user
from katalon.core.limiter import limiter
from katalon.core.models import PasswordResetToken, User
from katalon.database import get_db
from katalon.main import app


def _result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.fixture
def session() -> AsyncMock:
    value = AsyncMock()
    value.add = MagicMock()

    async def override_db():
        yield value

    app.dependency_overrides[get_db] = override_db
    yield value
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_password_reset_request_is_generic_and_queues_only_a_row_id(
    session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(id=uuid.uuid4(), email="admin@example.org", hashed_password=hash_password("Current123"), role="admin")
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "katalon_base_url", "https://katalon.example.org")
    session.execute = AsyncMock(side_effect=[_result(user), _result(None)])
    queued: list[object] = []

    with patch("katalon.api.v1.auth.enqueue", side_effect=lambda *args: queued.extend(args) or "task-id"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            known = await client.post("/v1/auth/password-reset", json={"email": user.email})

    session.execute = AsyncMock(return_value=_result(None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unknown = await client.post("/v1/auth/password-reset", json={"email": "missing@example.org"})

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    reset = next(call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], PasswordResetToken))
    from katalon.services.secret_service import decrypt_value

    token = decrypt_value(reset.delivery_token)
    assert reset.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token != reset.token_hash
    assert reset.request_hash == hashlib.sha256(user.id.bytes).hexdigest()
    assert queued == [ANY, str(reset.id)]
    session.commit.assert_awaited_once()
    assert "FOR UPDATE" in str(session.execute.await_args_list[0].args[0])


@pytest.mark.asyncio
async def test_password_reset_is_unavailable_without_mail_before_user_lookup(
    session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    limiter.reset()
    monkeypatch.setattr(settings, "smtp_enabled", False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/auth/password-reset", json={"email": "admin@example.org"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Passwort-Reset ist derzeit nicht verfügbar."}
    session.execute.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_password_reset_stays_generic_when_broker_is_down(
    session: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    limiter.reset()
    user = User(
        id=uuid.uuid4(),
        email="admin@example.org",
        hashed_password=hash_password("Current123"),
        role="admin",
        is_active=True,
    )
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "katalon_base_url", "https://katalon.example.org")
    session.execute = AsyncMock(side_effect=[_result(user), _result(None)])

    with patch("katalon.api.v1.auth.enqueue", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/v1/auth/password-reset", json={"email": user.email})

    assert response.status_code == 202
    reset = next(call.args[0] for call in session.add.call_args_list if isinstance(call.args[0], PasswordResetToken))
    session.delete.assert_awaited_once_with(reset)
    assert session.commit.await_count == 2

    session.execute = AsyncMock(return_value=_result(None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unknown = await client.post("/v1/auth/password-reset", json={"email": "missing@example.org"})
    assert unknown.status_code == 202
    assert session.add.call_count == 1


@pytest.mark.asyncio
async def test_password_reset_is_one_time_and_invalidates_existing_jwts(session: AsyncMock) -> None:
    token = "x" * 43
    user = User(id=uuid.uuid4(), email="admin@example.org", hashed_password=hash_password("Current123"), role="admin")
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=1),
    )
    old_access_token = create_access_token(user)
    session.execute = AsyncMock(side_effect=[_result(reset), _result(user)])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/auth/password-reset/confirm", json={"token": token, "new_password": "NewPass123"})

    assert response.status_code == 204
    assert verify_password("NewPass123", user.hashed_password)
    assert user.token_version == 1
    assert reset.used_at is not None
    session.execute = AsyncMock(return_value=_result(user))
    with pytest.raises(HTTPException, match="Could not validate credentials"):
        await get_current_user(old_access_token, None, session)


@pytest.mark.asyncio
async def test_pre_version_access_token_is_accepted_for_unrevoked_users(session: AsyncMock) -> None:
    user = User(
        id=uuid.uuid4(),
        email="admin@example.org",
        hashed_password=hash_password("Current123"),
        role="admin",
        is_active=True,
    )
    legacy = jwt.encode(
        {"sub": str(user.id), "role": user.role, "email": user.email, "typ": "access", "exp": datetime.now(UTC) + timedelta(minutes=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    session.execute = AsyncMock(return_value=_result(user))

    assert await get_current_user(legacy, None, session) is user
