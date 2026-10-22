# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import runpy
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import insert, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from katalon.core.models import MediaFile, Object


@pytest.mark.asyncio
async def test_iiif_identifier_lookup_uses_both_indexes(migrated_database: str) -> None:
    """Exercise the migrated schema and the auth gate's OR predicate at scale."""
    engine = create_async_engine(migrated_database)
    object_id = uuid.uuid4()
    prefix = str(object_id)
    expected_indexes = {"ix_media_files_storage_key", "ix_media_files_iiif_storage_key"}
    assert expected_indexes <= {index.name for index in MediaFile.__table__.indexes}
    try:
        async with engine.connect() as connection, connection.begin() as transaction:
            await connection.execute(insert(Object).values(id=object_id))
            rows = [
                {
                    "id": uuid.uuid4(),
                    "object_id": object_id,
                    "filename": f"image-{i}.jpg",
                    "mime_type": "image/jpeg",
                    "storage_key": f"{prefix}/{i}.jpg",
                    "iiif_storage_key": f"{prefix}/{i}_pyramid.tif" if i % 2 else None,
                    "deleted_at": datetime(2026, 1, 1) if i == 9999 else None,
                }
                for i in range(10000)
            ]
            await connection.execute(insert(MediaFile), rows)
            await connection.execute(text("ANALYZE media_files"))

            for identifier, expected_id in (
                (f"{prefix}/123.jpg", rows[123]["id"]),
                (f"{prefix}/123_pyramid.tif", rows[123]["id"]),
                (f"{prefix}/124.jpg", rows[124]["id"]),
                (f"{prefix}/9999_pyramid.tif", None),
                (f"{prefix}/missing.jpg", None),
            ):
                query = select(MediaFile).where(
                    (MediaFile.iiif_storage_key == identifier)
                    | (MediaFile.storage_key == identifier),
                    MediaFile.deleted_at.is_(None),
                )
                assert (await connection.execute(query)).scalar_one_or_none() == expected_id
                sql = query.compile(
                    dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True},
                )
                plan = (await connection.execute(text(f"EXPLAIN (FORMAT JSON) {sql}"))).scalar_one()
                nodes = [plan[0]["Plan"]]
                used_indexes = set()
                while nodes:
                    node = nodes.pop()
                    if "Index Name" in node:
                        used_indexes.add(node["Index Name"])
                    nodes.extend(node.get("Plans", []))
                assert expected_indexes <= used_indexes, plan
            # Shared test database: leave no representative media rows behind.
            await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_index_migration_recovers_invalid_build_and_preserves_operator_indexes(
    postgres_url: str,
) -> None:
    migration = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "migrations/versions/0084_media_identifier_indexes.py")
    )
    schema = f"test_media_indexes_{uuid.uuid4().hex}"
    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")

    def migrate(connection: Connection, direction: str) -> None:
        context = MigrationContext.configure(connection)
        with context.begin_transaction(), Operations.context(context):
            migration[direction]()

    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET search_path TO "{schema}"'))
            await connection.execute(text(
                "CREATE TABLE media_files (storage_key varchar(1024), iiif_storage_key varchar(1024))"
            ))
            await connection.execute(text("INSERT INTO media_files VALUES ('same', NULL), ('same', NULL)"))
            await connection.execute(text("CREATE INDEX perf_media_storage_key ON media_files (storage_key)"))
            # A failed concurrent unique build leaves a real invalid PostgreSQL index.
            with pytest.raises(IntegrityError):
                await connection.execute(text(
                    "CREATE UNIQUE INDEX CONCURRENTLY ix_media_files_storage_key "
                    "ON media_files (storage_key)"
                ))
            valid = text("SELECT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:name)")
            assert await connection.scalar(valid, {"name": "ix_media_files_storage_key"}) is False
            await connection.commit()
            await connection.run_sync(migrate, "upgrade")
            await connection.run_sync(migrate, "upgrade")
            for name in ("ix_media_files_storage_key", "ix_media_files_iiif_storage_key"):
                assert await connection.scalar(valid, {"name": name}) is True
            await connection.commit()
            await connection.run_sync(migrate, "downgrade")
            await connection.run_sync(migrate, "downgrade")
            for name in ("ix_media_files_storage_key", "ix_media_files_iiif_storage_key"):
                assert await connection.scalar(valid, {"name": name}) is None
            assert await connection.scalar(valid, {"name": "perf_media_storage_key"}) is True
    finally:
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
