# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Exercise the actual container entrypoint and two spawned Uvicorn workers."""

import asyncio
import os
import re
import signal
import socket
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


class _ImageServer(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args) -> None:
        pass


@pytest.mark.asyncio
async def test_entrypoint_initializes_once_before_two_workers(postgres_url, tmp_path) -> None:
    # First-run credentials need their own database, not the suite's shared admin account.
    database_name = f"workers_{uuid.uuid4().hex}"
    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    database_url = postgres_url.rsplit("/", 1)[0] + "/" + database_name
    image_server = ThreadingHTTPServer(("127.0.0.1", 0), _ImageServer)
    thread = threading.Thread(target=image_server.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    backend = Path(__file__).resolve().parents[2]
    credentials = tmp_path / "first-run.txt"
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "DEBUG": "true",
        "SECRET_KEY": "test-worker-jwt-key-at-least-32-characters",
        "KATALON_SECRETS_KEY": "test-katalon-secrets-key-32-chars",
        "KATALON_BASE_URL": "https://workers.example.org",
        "FIRST_RUN_CREDENTIALS_PATH": str(credentials),
        "MEDIA_ROOT": str(tmp_path),
        "CANTALOUPE_URL": f"http://127.0.0.1:{image_server.server_port}",
        "ELASTICSEARCH_URL": "http://127.0.0.1:9",
        "WEB_CONCURRENCY": "2",
        "DATABASE_POOL_SIZE": "2",
        "DATABASE_MAX_OVERFLOW": "0",
    }
    env.pop("KATALON_BOOTSTRAPPED", None)
    log = tmp_path / "workers.log"
    try:
        with log.open("w") as output:
            process = await asyncio.create_subprocess_exec(
                "sh", str(backend / "docker-entrypoint.sh"), "uvicorn", "katalon.main:app",
                "--host", "127.0.0.1", "--port", str(port),
                cwd=backend, env=env, stdout=output, stderr=output, start_new_session=True,
            )
            try:
                async with httpx.AsyncClient() as client:
                    for _ in range(150):
                        assert process.returncode is None, "API exited before both workers started"
                        content = log.read_text()
                        if content.count("Application startup complete.") >= 2:
                            response = await client.get(f"http://127.0.0.1:{port}/api/openapi.json")
                            assert response.status_code == 200
                            assert response.json()["info"]["title"] == "Katalon API"
                            break
                        await asyncio.sleep(0.2)
                    else:
                        pytest.fail("Two API workers did not become ready within 30 seconds")
                assert len(set(re.findall(r"Started server process \[(\d+)\]", content))) == 2
                # Repeated _ensure_admin() in worker lifespans used to remove this file.
                assert credentials.is_file()
            finally:
                if process.returncode is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        await asyncio.wait_for(process.wait(), timeout=15)
                    except TimeoutError:
                        os.killpg(process.pid, signal.SIGKILL)
                        await process.wait()
    finally:
        image_server.shutdown()
        image_server.server_close()
        thread.join(timeout=5)
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE "{database_name}" WITH (FORCE)'))
        await engine.dispose()
