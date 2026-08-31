import importlib
import os
import subprocess
from pathlib import Path

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
    connection — the task body never runs (no worker consumes it), matching the
    fire-and-forget contract of the request path."""
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
