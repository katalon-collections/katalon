# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Unit tests for the reset_admin management command."""
from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock, patch


def _make_fake_user(email: str = "admin@example.org", role: str = "superuser") -> MagicMock:
    user = MagicMock()
    user.id = "test-uuid"
    user.email = email
    user.role = role
    user.hashed_password = "old_hash"
    return user


def test_main_is_callable() -> None:
    mod = importlib.import_module("katalon.management.reset_admin")
    assert callable(mod.main)


def test_password_token_length() -> None:
    import secrets

    from katalon.management.reset_admin import PASSWORD_TOKEN_BYTES

    pw = secrets.token_urlsafe(PASSWORD_TOKEN_BYTES)
    assert len(pw) >= PASSWORD_TOKEN_BYTES


def test_reset_exits_when_no_admins(monkeypatch: object, capsys: object) -> None:
    import asyncio

    from katalon.management.reset_admin import _reset

    async def _fake_reset_inner() -> None:
        fake_scalars = MagicMock()
        fake_scalars.all.return_value = []

        fake_result = MagicMock()
        fake_result.scalars.return_value = fake_scalars

        fake_session = AsyncMock()
        fake_session.execute = AsyncMock(return_value=fake_result)
        fake_session.__aenter__ = AsyncMock(return_value=fake_session)
        fake_session.__aexit__ = AsyncMock(return_value=False)

        with patch("katalon.database.AsyncSessionLocal", return_value=fake_session):
            with patch("sys.exit", side_effect=SystemExit(1)) as mock_exit:
                try:
                    await _reset()
                except SystemExit:
                    pass
                mock_exit.assert_called_once_with(1)

    asyncio.run(_fake_reset_inner())
