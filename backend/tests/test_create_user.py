# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Unit tests for the create_user management command."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from katalon.management.create_user import _create


def _result(user: object | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    return result


def test_cli_forwards_credentials_and_role() -> None:
    from katalon.management.cli import cli

    with patch("katalon.management.cli.create_user_impl") as create_user_impl:
        result = CliRunner().invoke(
            cli,
            [
                "create-user",
                "--email",
                "cataloger@example.org",
                "--password",
                "Cataloger123",
                "--role",
                "cataloger",
            ],
        )

    assert result.exit_code == 0
    assert result.output == "Created user cataloger@example.org with role cataloger.\n"
    create_user_impl.assert_called_once_with(
        email="cataloger@example.org", password="Cataloger123", role="cataloger"
    )


@pytest.mark.asyncio
async def test_create_persists_hashed_credentials() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=_result(None))
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("katalon.database.AsyncSessionLocal", return_value=session),
        patch("katalon.api.v1.auth.hash_password", return_value="hashed-password"),
    ):
        await _create("cataloger@example.org", "Cataloger123", "cataloger")

    created = session.add.call_args.args[0]
    assert created.email == "cataloger@example.org"
    assert created.role == "cataloger"
    assert created.hashed_password == "hashed-password"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_rejects_duplicate_email() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=_result(object()))
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    with patch("katalon.database.AsyncSessionLocal", return_value=session):
        with pytest.raises(ValueError, match="E-Mail bereits vergeben"):
            await _create("cataloger@example.org", "Cataloger123", "cataloger")

    session.add.assert_not_called()
    session.commit.assert_not_awaited()
