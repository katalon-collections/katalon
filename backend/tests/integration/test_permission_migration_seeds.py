# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_fresh_migrations_seed_default_permissions(migrated_database: str) -> None:
    """A new database receives the permission matrix through Alembic upgrades."""
    engine = create_async_engine(migrated_database)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM role_permissions), "
                    "(SELECT count(*) FROM feature_permissions)"
                )
            )
            assert result.one() == (60, 24)
    finally:
        await engine.dispose()
