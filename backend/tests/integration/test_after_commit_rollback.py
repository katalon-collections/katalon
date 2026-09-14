# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Integration tests for after_commit rollback and dispatch guarantees (#392).

Verifies that side effects (Elasticsearch indexing, removal, RDF sync, relation
cleanup) registered via ``after_commit``:
1. Are discarded entirely on database rollback or request failure — 0 Celery
   tasks enqueued, 0 worker handlers executed, 0 Elasticsearch documents,
   0 RDF projections, and 0 cleanup executions.
2. Are dispatched and processed by a consuming/eager test double after a
   successful commit, where the worker sees and processes durably committed
   database state.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from katalon.core.models import Entity, FieldDefinition, Object, Procedure, Relation
from katalon.workers.celery_app import celery_app
from katalon.workers.index_tasks import (
    bulk_reindex_type_task,
    cascade_reindex_task,
    index_record_task,
    remove_record_task,
)
from katalon.workers.rdf_tasks import (
    remove_rdf_record_task,
    sync_rdf_record_task,
)


class _TaskResult:
    """Minimal AsyncResult duck-type for Celery task dispatch."""

    def __init__(self, task_id: str) -> None:
        self.id = task_id


class ConsumingWorkerDouble:
    """In-process consuming worker test-double for Celery background tasks.

    Intercepts `.delay()` calls produced by ``katalon.workers.enqueue`` after a
    commit. For each dispatched task, it executes an in-process consumer that
    verifies Postgres visibility from an independent database session and
    maintains in-memory stores for Elasticsearch documents, RDF projections,
    and cleanup operations.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self.dispatched_tasks: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.es_documents: dict[str, dict[str, Any]] = {}
        self.rdf_projections: set[tuple[str, str]] = set()
        self.cleanup_tasks: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.worker_saw_committed_row: dict[str, bool] = {}
        self._pending_tasks: list[asyncio.Task[None]] = []

    def make_handler(self, task_name: str) -> Any:
        def _delay(*args: Any, **kwargs: Any) -> _TaskResult:
            task_id = f"tid-{uuid.uuid4().hex[:8]}"
            self.dispatched_tasks.append((task_name, args, kwargs))
            coro = self._consume(task_name, args, kwargs)
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(coro)
                self._pending_tasks.append(task)
            except RuntimeError:
                pass
            return _TaskResult(task_id)

        return _delay

    async def _consume(
        self, task_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> None:
        from katalon.workers.index_tasks import _record_models

        async with self.session_factory() as session:
            if task_name == "katalon.index_record":
                record_type, record_id, doc = str(args[0]), str(args[1]), args[2]
                model = _record_models().get(record_type)
                if model is not None:
                    row = await session.get(model, uuid.UUID(record_id))
                    self.worker_saw_committed_row[record_id] = row is not None
                self.es_documents[record_id] = {"record_type": record_type, **doc}
            elif task_name == "katalon.remove_record":
                record_id = str(args[0])
                self.es_documents.pop(record_id, None)
            elif task_name == "katalon.sync_rdf_record":
                record_type, record_id = str(args[0]), str(args[1])
                self.rdf_projections.add((record_type, record_id))
            elif task_name == "katalon.remove_rdf_record":
                record_type, record_id = str(args[0]), str(args[1])
                self.rdf_projections.discard((record_type, record_id))
            elif "cleanup" in task_name or task_name == "katalon.bulk_reindex_type":
                self.cleanup_tasks.append((task_name, args, kwargs))

    async def drain(self) -> None:
        """Wait for all scheduled background worker tasks to complete."""
        while self._pending_tasks:
            pending = list(self._pending_tasks)
            self._pending_tasks.clear()
            await asyncio.gather(*pending)


@pytest.fixture
def consuming_worker(monkeypatch: pytest.MonkeyPatch) -> ConsumingWorkerDouble:
    import katalon.database as database_module

    worker = ConsumingWorkerDouble(database_module.AsyncSessionLocal)
    monkeypatch.setattr(
        index_record_task, "delay", worker.make_handler("katalon.index_record")
    )
    monkeypatch.setattr(
        remove_record_task, "delay", worker.make_handler("katalon.remove_record")
    )
    monkeypatch.setattr(
        cascade_reindex_task, "delay", worker.make_handler("katalon.cascade_reindex")
    )
    monkeypatch.setattr(
        bulk_reindex_type_task, "delay", worker.make_handler("katalon.bulk_reindex_type")
    )
    monkeypatch.setattr(
        sync_rdf_record_task, "delay", worker.make_handler("katalon.sync_rdf_record")
    )
    monkeypatch.setattr(
        remove_rdf_record_task, "delay", worker.make_handler("katalon.remove_rdf_record")
    )
    return worker


@pytest.mark.asyncio
async def test_api_create_object_rollback_leaves_zero_tasks_and_zero_es_docs(
    app: Any,
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    consuming_worker: ConsumingWorkerDouble,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When an API request fails before or during session.commit(), after_commit
    hooks are discarded: no tasks enqueued, 0 ES documents, 0 projections."""
    import katalon.database as database_module
    from katalon.config import settings

    monkeypatch.setattr(settings, "oxigraph_enabled", True)

    idno = f"ROLLBACK-OBJ-{uuid.uuid4().hex[:10]}"

    async def _failing_commit(self: AsyncSession) -> None:
        raise RuntimeError("Simulated database commit failure")

    monkeypatch.setattr(AsyncSession, "commit", _failing_commit)

    try:
        response = await async_client.post(
            "/v1/objects",
            headers=auth_headers,
            json={
                "idno": idno,
                "status": "draft",
                "metadata_": {"title": [{"value": "Will be rolled back", "lang": "de"}]},
            },
        )
        assert response.status_code >= 500
    except RuntimeError as exc:
        assert "Simulated database commit failure" in str(exc)

    await consuming_worker.drain()

    # 1. Verify row was not committed in Postgres
    async with database_module.AsyncSessionLocal() as session:
        result = await session.execute(select(Object).where(Object.idno == idno))
        assert result.scalar_one_or_none() is None

    # 2. Verify 0 tasks enqueued / dispatched
    assert consuming_worker.dispatched_tasks == []

    # 3. Verify 0 Elasticsearch documents created
    assert len(consuming_worker.es_documents) == 0

    # 4. Verify 0 RDF projections created
    assert len(consuming_worker.rdf_projections) == 0

    # 5. Verify 0 cleanup tasks
    assert len(consuming_worker.cleanup_tasks) == 0


@pytest.mark.asyncio
async def test_api_create_object_commit_dispatches_and_worker_processes_committed_data(
    app: Any,
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    consuming_worker: ConsumingWorkerDouble,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When an API request succeeds and session commits, after_commit hooks are
    dispatched and the consuming worker processes the committed row."""
    import katalon.database as database_module
    from katalon.config import settings

    monkeypatch.setattr(settings, "oxigraph_enabled", True)

    idno = f"COMMIT-OBJ-{uuid.uuid4().hex[:10]}"
    create_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": "draft",
            "metadata_": {"title": [{"value": "Successfully committed", "lang": "de"}]},
        },
    )
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    await consuming_worker.drain()

    # 1. Verify row exists in Postgres
    async with database_module.AsyncSessionLocal() as session:
        obj = await session.get(Object, uuid.UUID(created_id))
        assert obj is not None
        assert obj.idno == idno

    # 2. Verify task was dispatched and consumed
    dispatched_names = [name for name, _args, _kwargs in consuming_worker.dispatched_tasks]
    assert "katalon.index_record" in dispatched_names
    assert "katalon.sync_rdf_record" in dispatched_names

    # 3. Verify worker saw the committed row in Postgres from its independent session
    assert consuming_worker.worker_saw_committed_row.get(created_id) is True

    # 4. Verify Elasticsearch document store received the document
    assert created_id in consuming_worker.es_documents
    doc = consuming_worker.es_documents[created_id]
    assert doc["record_type"] == "object"
    assert doc.get("idno") == idno

    # 5. Verify RDF projection was recorded
    assert ("object", created_id) in consuming_worker.rdf_projections


@pytest.mark.asyncio
async def test_get_db_session_flow_rollback_after_index_record_discards_hooks(
    app: Any, consuming_worker: ConsumingWorkerDouble, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulates an unhandled exception inside a get_db() block occurring AFTER
    index_record has registered hooks via after_commit. Verifies hooks are discarded."""
    import katalon.database as database_module
    from katalon.config import settings
    from katalon.database import get_db
    from katalon.services import search_service

    monkeypatch.setattr(settings, "oxigraph_enabled", True)

    idno = f"DB-ROLLBACK-{uuid.uuid4().hex[:10]}"
    record_id = uuid.uuid4()

    with pytest.raises(RuntimeError, match="Crash after index_record registered"):
        async for db in get_db():
            obj = Object(
                id=record_id,
                idno=idno,
                status="draft",
                metadata_={"title": [{"value": "Direct DB rollback", "lang": "de"}]},
            )
            db.add(obj)
            await db.flush()

            # after_commit attaches hooks to db.info
            await search_service.index_record("object", obj, db)
            assert "katalon_after_commit_hooks" in db.info
            assert len(db.info["katalon_after_commit_hooks"]) >= 1

            # Crash before generator reaches commit()
            raise RuntimeError("Crash after index_record registered")

    await consuming_worker.drain()

    # Verify DB rollback
    async with database_module.AsyncSessionLocal() as session:
        assert await session.get(Object, record_id) is None

    # Zero tasks dispatched, zero documents, zero projections
    assert consuming_worker.dispatched_tasks == []
    assert len(consuming_worker.es_documents) == 0
    assert len(consuming_worker.rdf_projections) == 0
    assert len(consuming_worker.cleanup_tasks) == 0


@pytest.mark.asyncio
async def test_get_db_session_flow_commit_executes_hooks_with_committed_data(
    app: Any, consuming_worker: ConsumingWorkerDouble, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies that normal exit from get_db() commits and executes after_commit hooks."""
    import katalon.database as database_module
    from katalon.config import settings
    from katalon.database import get_db
    from katalon.services import search_service

    monkeypatch.setattr(settings, "oxigraph_enabled", True)

    idno = f"DB-COMMIT-{uuid.uuid4().hex[:10]}"
    record_id = uuid.uuid4()

    async for db in get_db():
        obj = Object(
            id=record_id,
            idno=idno,
            status="draft",
            metadata_={"title": [{"value": "Direct DB commit", "lang": "de"}]},
        )
        db.add(obj)
        await db.flush()
        await search_service.index_record("object", obj, db)

    await consuming_worker.drain()

    # Verify committed in Postgres
    async with database_module.AsyncSessionLocal() as session:
        row = await session.get(Object, record_id)
        assert row is not None
        assert row.idno == idno

    # Verify worker consumed and indexed
    str_id = str(record_id)
    assert str_id in consuming_worker.es_documents
    assert consuming_worker.worker_saw_committed_row.get(str_id) is True
    assert ("object", str_id) in consuming_worker.rdf_projections


@pytest.mark.asyncio
async def test_api_delete_object_rollback_does_not_remove_es_doc(
    app: Any,
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    consuming_worker: ConsumingWorkerDouble,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When deleting an object fails on commit, remove_record is not dispatched,
    the document remains in Elasticsearch, and the object is not soft-deleted."""
    import katalon.database as database_module

    # 1. Create and commit an object first
    idno = f"DEL-ROLLBACK-{uuid.uuid4().hex[:10]}"
    create_res = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": idno, "status": "draft", "metadata_": {}},
    )
    assert create_res.status_code == 201
    object_id = create_res.json()["id"]
    await consuming_worker.drain()
    assert object_id in consuming_worker.es_documents

    # Clear dispatched history to isolate delete checks
    consuming_worker.dispatched_tasks.clear()

    # 2. Attempt delete with failing commit
    async def _failing_commit(self: AsyncSession) -> None:
        raise RuntimeError("Commit failed during delete")

    monkeypatch.setattr(AsyncSession, "commit", _failing_commit)

    try:
        res = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
        assert res.status_code >= 500
    except RuntimeError:
        pass

    await consuming_worker.drain()

    # 3. Object in DB is NOT soft-deleted
    async with database_module.AsyncSessionLocal() as session:
        obj = await session.get(Object, uuid.UUID(object_id))
        assert obj is not None
        assert obj.deleted_at is None

    # 4. No remove_record task was dispatched
    dispatched_names = [name for name, _args, _kwargs in consuming_worker.dispatched_tasks]
    assert "katalon.remove_record" not in dispatched_names

    # 5. Document remains in ES store
    assert object_id in consuming_worker.es_documents


@pytest.mark.asyncio
async def test_api_delete_object_commit_removes_es_doc(
    app: Any,
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    consuming_worker: ConsumingWorkerDouble,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When deleting an object commits successfully, remove_record is dispatched
    and removes the document from Elasticsearch."""
    import katalon.database as database_module
    from katalon.config import settings

    monkeypatch.setattr(settings, "oxigraph_enabled", True)

    # 1. Create and commit an object
    idno = f"DEL-COMMIT-{uuid.uuid4().hex[:10]}"
    create_res = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": idno, "status": "draft", "metadata_": {}},
    )
    assert create_res.status_code == 201
    object_id = create_res.json()["id"]
    await consuming_worker.drain()
    assert object_id in consuming_worker.es_documents
    assert ("object", object_id) in consuming_worker.rdf_projections

    # 2. Delete successfully
    delete_res = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_res.status_code == 204

    await consuming_worker.drain()

    # 3. Object in DB is soft-deleted
    async with database_module.AsyncSessionLocal() as session:
        obj = await session.get(Object, uuid.UUID(object_id))
        assert obj is not None
        assert obj.deleted_at is not None

    # 4. remove_record was consumed and document removed
    assert object_id not in consuming_worker.es_documents
    assert ("object", object_id) not in consuming_worker.rdf_projections


@pytest.mark.asyncio
async def test_procedure_hard_delete_relation_cleanup_rollback_leaves_zero_cleanup_tasks(
    app: Any,
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    consuming_worker: ConsumingWorkerDouble,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When hard-deleting a procedure fails on commit, relation cleanup reindexing
    and removal tasks are discarded, and the referencing entity relations remain untouched."""
    import katalon.database as database_module

    marker = uuid.uuid4().hex[:8]
    procedure_id = uuid.uuid4()
    field_name = f"proc_ref_{marker}"

    async with database_module.AsyncSessionLocal() as session:
        session.add_all(
            [
                FieldDefinition(
                    target_type="entity",
                    name=field_name,
                    label={"de": "Vorgang"},
                    field_type="relation",
                    settings={"target_type": "procedure"},
                ),
                Procedure(
                    id=procedure_id,
                    idno=f"PROC-{marker}",
                    procedure_type="loan_out",
                    status="draft",
                    metadata_={},
                ),
            ]
        )
        entity = Entity(
            idno=f"ENT-{marker}",
            entity_type="person",
            status="draft",
            metadata_={field_name: {"id": str(procedure_id), "label": "Procedure"}},
        )
        session.add(entity)
        await session.flush()
        entity_id = entity.id
        session.add(
            Relation(
                from_type="entity",
                from_id=entity_id,
                to_type="procedure",
                to_id=procedure_id,
                relation_type="references",
            )
        )
        await session.commit()

    consuming_worker.dispatched_tasks.clear()

    # Simulate failure on commit
    async def _failing_commit(self: AsyncSession) -> None:
        raise RuntimeError("Commit failed during procedure delete")

    monkeypatch.setattr(AsyncSession, "commit", _failing_commit)

    try:
        res = await async_client.delete(
            f"/v1/procedures/{procedure_id}?force=true", headers=auth_headers
        )
        assert res.status_code >= 500
    except RuntimeError:
        pass

    await consuming_worker.drain()

    # Verify procedure still exists and entity relation is intact in DB
    async with database_module.AsyncSessionLocal() as session:
        assert await session.get(Procedure, procedure_id) is not None
        ent = await session.get(Entity, entity_id)
        assert ent is not None
        assert ent.metadata_.get(field_name) == {
            "id": str(procedure_id),
            "label": "Procedure",
        }

    # Zero tasks dispatched, zero documents in store
    assert consuming_worker.dispatched_tasks == []
    assert len(consuming_worker.es_documents) == 0


@pytest.mark.asyncio
async def test_celery_native_task_always_eager_with_after_commit(
    app: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies that Celery's native task_always_eager mode works seamlessly with
    after_commit / run_after_commit_hooks: eager task is NOT called on rollback,
    and IS called synchronously on commit."""
    from katalon.database import get_db
    from katalon.workers.enqueue import after_commit

    task_executions: list[dict[str, Any]] = []

    def _raw_eager_task(record_type: str, record_id: str) -> str:
        task_executions.append({"record_type": record_type, "record_id": record_id})
        return "done"

    _eager_task: Any = celery_app.task(name="test.eager_verification_task")(_raw_eager_task)

    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)

    rec_id = str(uuid.uuid4())

    # 1. Rollback case: task should not execute
    with pytest.raises(ValueError, match="Rollback test"):
        async for db in get_db():
            after_commit(db, _eager_task, "object", rec_id)
            raise ValueError("Rollback test")

    assert task_executions == []

    # 2. Commit case: task should execute eagerly during run_after_commit_hooks
    async for db in get_db():
        after_commit(db, _eager_task, "object", rec_id)

    assert len(task_executions) == 1
    assert task_executions[0] == {"record_type": "object", "record_id": rec_id}
