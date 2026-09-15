# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import asyncio
import os
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from katalon.management.db_reset import _do_reset

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_full_reset_restores_default_permissions(postgres_url: str) -> None:
    """An explicit full reset leaves the new instance with usable role defaults.

    Uses a separate database so truncating all tables does not corrupt the
    session-wide test database for subsequent integration tests.
    """
    admin_url = postgres_url.rsplit("/", 1)[0] + "/postgres"
    temp_db_name = f"test_reset_{uuid.uuid4().hex[:8]}"

    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{temp_db_name}"'))
    finally:
        await admin_engine.dispose()

    test_db_url = postgres_url.rsplit("/", 1)[0] + f"/{temp_db_name}"
    env = os.environ.copy()
    env["DATABASE_URL"] = test_db_url
    env.setdefault("KATALON_SECRETS_KEY", "test-katalon-secrets-key-32-chars")

    await asyncio.to_thread(
        subprocess.run,
        ["python", "-m", "alembic", "-c", "migrations/alembic.ini", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
    )

    test_engine = create_async_engine(test_db_url)
    try:
        truncated = await _do_reset(test_engine, wipe_all=True)
        assert {"role_permissions", "feature_permissions"} <= set(truncated)
        async with test_engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM role_permissions), "
                    "(SELECT count(*) FROM feature_permissions)"
                )
            )
            assert result.one() == (60, 24)
    finally:
        await test_engine.dispose()
        admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with admin_engine.connect() as conn:
                await conn.execute(text(f'DROP DATABASE IF EXISTS "{temp_db_name}" WITH (FORCE)'))
        finally:
            await admin_engine.dispose()
