# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Sessions on a private NullPool engine, for code that runs outside the API's event loop.

Celery tasks each run in their own ``asyncio.run`` loop (and, with ``--pool=threads``, their own
thread). The pooled global engine in ``katalon.database`` would hand out connections bound to a
previous run's loop, and leave them open server-side once that loop is gone. Worker code therefore
never imports ``katalon.database`` (enforced by ``tests/test_architecture.py``) and opens its
sessions here instead. ``application_name`` shows the owner in ``pg_stat_activity``.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def make_session(
    application_name: str = "katalon-worker",
) -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    """Per-run NullPool engine plus its sessionmaker. The caller must dispose the engine
    (``engine_scope``)."""
    # Imported at call time: the test harness reloads katalon.config per test session to pick up
    # the ephemeral testcontainer DB URL, and a module-level import would keep a stale Settings.
    from katalon.config import settings

    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={"server_settings": {"application_name": application_name}},
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


@asynccontextmanager
async def engine_scope(engine: AsyncEngine) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await engine.dispose()


@asynccontextmanager
async def isolated_session(application_name: str = "katalon-worker") -> AsyncIterator[AsyncSession]:
    """One session on its own NullPool engine, disposed on exit."""
    session_factory, engine = make_session(application_name)
    async with engine_scope(engine), session_factory() as session:
        yield session
