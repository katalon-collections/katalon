# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Regression tests for pool_pre_ping on the central database engine (#pool-pre-ping).

Without pool_pre_ping, a pooled connection killed server-side (DB container
restart, OOM, pg_terminate_backend, idle timeout) is handed back out as-is
and the next query on it fails. pool_pre_ping pings on checkout and silently
replaces dead connections.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from katalon.database import engine as production_engine


def test_production_engine_has_pool_pre_ping_enabled() -> None:
    assert production_engine.pool._pre_ping is True


@pytest.mark.asyncio
async def test_session_survives_server_side_termination_of_pooled_connection(
    migrated_database: str,
) -> None:
    """A connection killed server-side while idle in the pool must not surface
    as a failure on the next checkout.

    Uses a dedicated pool_size=1 engine (mirroring the production engine's
    config) so the exact same underlying connection is guaranteed to be
    reused across checkouts.
    """
    test_engine = create_async_engine(
        migrated_database,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(test_engine)

    # Separate connection (NullPool, no reuse) so terminating the target
    # connection can't accidentally kill this connection instead.
    killer_engine = create_async_engine(migrated_database, poolclass=NullPool)
    killer_factory = async_sessionmaker(killer_engine)

    try:
        async with session_factory() as session:
            pid = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()

        async with killer_factory() as killer:
            await killer.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
            await killer.commit()

        async with session_factory() as session:
            assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await test_engine.dispose()
        await killer_engine.dispose()
