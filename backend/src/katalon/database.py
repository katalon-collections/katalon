# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from katalon.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Request-scoped session: commits after the endpoint returns successfully,
    rolls back on any exception. Side effects (ES indexing, RDF sync, relation
    cleanup) that depend on this request's write MUST be registered via
    ``katalon.workers.enqueue.after_commit`` rather than dispatched directly —
    they are only actually enqueued here, after ``commit()`` has succeeded
    (#392). A rollback discards them without ever dispatching.

    The ``workers.enqueue`` import is local, not module-level: ``core.models``
    imports this module for ``Base``, and ``core*`` must never depend on
    ``workers*`` (test_architecture.py) — a module-level import here would
    make every ``core`` consumer transitively import Celery task modules.
    """
    from katalon.workers.enqueue import discard_after_commit_hooks, run_after_commit_hooks

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            await run_after_commit_hooks(session)
        except Exception:
            discard_after_commit_hooks(session)
            await session.rollback()
            raise
