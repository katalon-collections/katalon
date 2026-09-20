# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import inspect
from collections.abc import AsyncGenerator
from contextvars import ContextVar

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

class SessionHolder:
    def __init__(self) -> None:
        self.session: AsyncSession | None = None


_request_session_holder_var: ContextVar[SessionHolder | None] = ContextVar(
    "request_session_holder", default=None
)


def register_current_session(session: AsyncSession) -> None:
    """Register the active database session for the current request context."""
    holder = _request_session_holder_var.get()
    if holder is not None:
        holder.session = session


def get_current_session() -> AsyncSession | None:
    """Return the database session registered for the current request, if any."""
    holder = _request_session_holder_var.get()
    return holder.session if holder is not None else None


async def commit_current_session() -> None:
    """Commit the database session active in the current request context, if any,
    and flush after_commit hooks immediately.

    Called by DatabaseCommitMiddleware BEFORE the HTTP response is transmitted
    to the client socket, preventing read-after-write race conditions where an
    immediate client-side refetch observes pre-commit database state.
    """
    from katalon.workers.enqueue import run_after_commit_hooks

    session = get_current_session()
    if session is not None and session.is_active:
        in_tx = session.in_transaction()
        if inspect.isawaitable(in_tx):
            in_tx = await in_tx
        if in_tx:
            await session.commit()
        await run_after_commit_hooks(session)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession]:
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
        register_current_session(session)
        try:
            yield session
            if session.is_active:
                in_tx = session.in_transaction()
                if inspect.isawaitable(in_tx):
                    in_tx = await in_tx
                if in_tx:
                    await session.commit()
                await run_after_commit_hooks(session)
        except Exception:
            discard_after_commit_hooks(session)
            await session.rollback()
            raise



