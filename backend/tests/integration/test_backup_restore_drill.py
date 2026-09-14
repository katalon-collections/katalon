# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Automated backup/restore drill (katalon issue #382).

Proves the documented restore procedure (almanac: Backup And Restore) works
mechanically: dump a populated database with pg_dump, restore it into a
fresh, unrelated Postgres instance with psql, and verify records and their
relations survive. This does not touch real production/staging backups — it
exercises the same pg_dump/psql commands against disposable containers.

pg_dump/psql run inside throwaway `postgis/postgis:16-3.4` containers on the
host network (`docker run --network host`), reaching the testcontainers'
host-mapped ports exactly like the test process itself does — the same "run
the client inside the matching server image" approach `docker/backup.sh`
uses in production, so this needs no host-installed PostgreSQL client and
can never drift to a mismatched major version.

Requires a working Docker daemon with host networking (Linux; this is what
`.github/workflows/backup-drill.yml` runs on). Runs on a schedule, not on
every push — see the `backup_drill` marker registered in pyproject.toml.
"""

from __future__ import annotations

import asyncio
import subprocess
import uuid
from urllib.parse import urlsplit

import asyncpg
import pytest
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.backup_drill

_PG_CLIENT_IMAGE = "postgis/postgis:16-3.4"


def _run_pg_client(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["docker", "run", "--rm", "-i", "--network", "host", "-e", "PGPASSWORD=katalon", _PG_CLIENT_IMAGE, *args],
        input=input_text,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout


@pytest.mark.asyncio
async def test_pg_dump_restore_preserves_records_and_relations(
    async_client, auth_headers, migrated_database: str
) -> None:
    marker = uuid.uuid4().hex[:12]

    collection = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={"idno": f"DRILL-COL-{marker}", "metadata_": {"label": "Drill collection"}},
    )
    assert collection.status_code == 201, collection.text
    collection_id = collection.json()["id"]

    obj = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"DRILL-OBJ-{marker}", "metadata_": {"label": "Drill object"}},
    )
    assert obj.status_code == 201, obj.text
    object_id = obj.json()["id"]

    relation = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "collection",
            "to_id": collection_id,
            "relation_type": "member_of",
        },
    )
    assert relation.status_code == 201, relation.text

    source = urlsplit(migrated_database.replace("postgresql+asyncpg://", "postgresql://"))

    dump = await asyncio.to_thread(
        _run_pg_client,
        [
            "pg_dump", "-h", source.hostname, "-p", str(source.port), "-U", "katalon",
            source.path.lstrip("/"), "--no-owner", "--no-privileges",
            # tiger/tiger_data/topology are bootstrapped by the postgis extension
            # itself on both source and target images — dumping them collides
            # with the target's own bootstrap ("schema already exists").
            "--exclude-schema=tiger", "--exclude-schema=tiger_data", "--exclude-schema=topology",
        ],
    )

    with PostgresContainer(
        image=_PG_CLIENT_IMAGE, username="katalon", password="katalon", dbname="restore_drill"
    ) as restored:
        target_host = restored.get_container_host_ip()
        target_port = restored.get_exposed_port(5432)

        await asyncio.to_thread(
            _run_pg_client,
            [
                "psql", "-h", target_host, "-p", str(target_port), "-U", "katalon",
                "-d", "restore_drill", "-v", "ON_ERROR_STOP=1",
            ],
            input_text=dump,
        )

        conn = await asyncpg.connect(
            host=target_host, port=target_port, user="katalon", password="katalon",
            database="restore_drill",
        )
        try:
            restored_object = await conn.fetchrow(
                "SELECT id FROM objects WHERE idno = $1", f"DRILL-OBJ-{marker}"
            )
            restored_collection = await conn.fetchrow(
                "SELECT id FROM collections WHERE idno = $1", f"DRILL-COL-{marker}"
            )
            assert restored_object is not None
            assert restored_collection is not None
            restored_relation = await conn.fetchrow(
                "SELECT relation_type FROM relations WHERE from_id = $1 AND to_id = $2",
                restored_object["id"],
                restored_collection["id"],
            )
            assert restored_relation is not None
            assert restored_relation["relation_type"] == "member_of"
        finally:
            await conn.close()
