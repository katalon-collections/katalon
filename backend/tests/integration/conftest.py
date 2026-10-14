# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import importlib
import os
import subprocess
from pathlib import Path
from typing import Any

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TEST_SECRETS_KEY = "test-katalon-secrets-key-32-chars"

os.environ["DEBUG"] = "true"


def _to_asyncpg(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest.fixture(scope="session")
def postgres_url() -> str:
    with PostgresContainer(
        image="postgis/postgis:16-3.4",
        username="katalon",
        password="katalon",
        dbname="katalon_test",
    ) as container:
        yield _to_asyncpg(container.get_connection_url())


@pytest.fixture(scope="session")
def migrated_database(postgres_url: str) -> str:
    env = os.environ.copy()
    env["DATABASE_URL"] = postgres_url
    env.setdefault("KATALON_SECRETS_KEY", TEST_SECRETS_KEY)

    subprocess.run(
        ["python", "-m", "alembic", "-c", "migrations/alembic.ini", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
    )

    return postgres_url


@pytest.fixture(scope="session", autouse=True)
def _celery_without_redis():
    """Integration tests bring up Postgres but no Redis. Point Celery at an
    in-memory broker so ``.delay()`` enqueues (and returns) without a broker
    connection — by default the task body never runs (no worker consumes it).
    Tests verifying worker execution, post-commit side effects, and rollback
    guarantees (e.g. ``test_after_commit_rollback.py``) plug in a consuming or
    eager test double to verify post-commit processing and zero-dispatch on
    rollback (#392)."""
    from katalon.workers.celery_app import celery_app

    celery_app.conf.broker_url = "memory://"
    celery_app.conf.result_backend = "cache+memory://"
    yield


@pytest.fixture
async def app(migrated_database: str, monkeypatch: pytest.MonkeyPatch):
    os.environ["DATABASE_URL"] = migrated_database
    os.environ["DEBUG"] = "true"
    os.environ.setdefault("KATALON_SECRETS_KEY", TEST_SECRETS_KEY)

    import katalon.config as config_module
    import katalon.database as database_module
    import katalon.integrations.elasticsearch as elasticsearch_module
    import katalon.main as main_module
    from katalon.core.limiter import limiter

    importlib.reload(config_module)
    importlib.reload(database_module)
    importlib.reload(main_module)

    async def _skip_cantaloupe_health() -> None:
        return None

    async def _skip_elasticsearch_setup() -> None:
        return None

    # SlowAPI keeps counters at module scope, while each test gets a fresh app.
    # Keep those test apps isolated without disabling the production limiter.
    limiter.reset()
    main_module._check_cantaloupe_health = _skip_cantaloupe_health
    monkeypatch.setattr(elasticsearch_module, "ensure_index", _skip_elasticsearch_setup)

    yield main_module.app

    # Each reload swaps in a fresh engine bound to this test's event loop.
    # Dispose it so its pooled asyncpg connections don't leak into the next
    # test's (different) loop — that causes "attached to a different loop".
    await database_module.engine.dispose()


@pytest.fixture
async def async_client(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client


@pytest.fixture
async def auth_headers(async_client: AsyncClient) -> dict[str, str]:
    response = await async_client.post(
        "/v1/auth/token",
        data={"username": "admin@katalon.dev", "password": "admin"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class FakeES:
    """Just enough of the ES surface the bulk/full reindex touches, with
    physical indices and one alias (starts as a legacy concrete index)."""

    def __init__(self) -> None:
        from katalon.integrations.elasticsearch import INDEX_NAME

        self.name = INDEX_NAME
        self.indices_data: dict[str, dict[str, dict[str, Any]]] = {INDEX_NAME: {}}
        self.alias_target: str | None = None  # None: name is a concrete index
        self.batch_sizes: list[int] = []
        self.on_first_batch: Any = None
        self.indices = _FakeIndices(self)

    def resolve(self, index: str) -> str:
        return self.alias_target if index == self.name and self.alias_target else index

    @property
    def docs(self) -> dict[str, dict[str, Any]]:
        return self.indices_data[self.resolve(self.name)]

    async def close(self) -> None:
        return None


class _FakeIndices:
    def __init__(self, es: FakeES) -> None:
        self.es = es

    async def refresh(self, **_kwargs: Any) -> None:
        return None

    async def create(self, index: str, body: Any = None, **_kwargs: Any) -> None:
        assert index not in self.es.indices_data
        self.es.indices_data[index] = {}
        if body and self.es.name in (body.get("aliases") or {}):
            self.es.alias_target = index

    async def exists(self, index: str) -> bool:
        return self.es.resolve(index) in self.es.indices_data

    async def put_alias(self, index: str, name: str) -> None:
        self.es.alias_target = index

    async def exists_alias(self, name: str) -> bool:
        return name == self.es.name and self.es.alias_target is not None

    async def get_alias(self, name: str) -> Any:
        class _Resp:
            body = {self.es.alias_target: {"aliases": {name: {}}}}

        return _Resp()

    async def update_aliases(self, body: dict[str, Any]) -> None:
        for action in body["actions"]:
            if "remove_index" in action:
                del self.es.indices_data[action["remove_index"]["index"]]
            elif "add" in action:
                self.es.alias_target = action["add"]["index"]

    async def delete(self, index: str) -> None:
        self.es.indices_data.pop(index, None)


@pytest.fixture
def fake_es(monkeypatch: pytest.MonkeyPatch) -> FakeES:
    """In-memory stand-in for the ES calls of the bulk and full reindex."""
    es = FakeES()
    import katalon.integrations.elasticsearch as es_module

    async def bulk_index_documents(_es, target_type, docs, *, index=es.name, **_kwargs):
        es.batch_sizes.append(len(docs))
        if es.on_first_batch is not None:
            hook, es.on_first_batch = es.on_first_batch, None
            await hook()
        target = es.indices_data[es.resolve(index)]
        for doc_id, body in docs:
            target[doc_id] = {"record_type": target_type, **body}
        return len(docs), []

    async def list_ids_by_type(record_type, **_kwargs):
        return {i for i, d in es.docs.items() if d.get("record_type") == record_type}

    async def delete_documents(_es, ids, *, index=es.name):
        ids = list(ids)
        target = es.indices_data[es.resolve(index)]
        for doc_id in ids:
            target.pop(doc_id, None)
        return len(ids)

    monkeypatch.setattr(es_module, "get_es", lambda: es)
    monkeypatch.setattr(es_module, "bulk_index_documents", bulk_index_documents)
    monkeypatch.setattr(es_module, "list_ids_by_type", list_ids_by_type)
    monkeypatch.setattr(es_module, "delete_documents", delete_documents)
    return es


@pytest.fixture
def fake_reindex_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeServer:
    """In-memory Redis for reindex coordination (no broker in integration tests)."""
    from katalon.workers import reindex_state

    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        reindex_state,
        "redis_client",
        lambda: fakeredis.FakeRedis(server=server, decode_responses=True),
    )
    return server
