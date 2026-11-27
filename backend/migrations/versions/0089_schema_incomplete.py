# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add schema_incomplete flag to all core record tables

Revision ID: 0089
Revises: 0088
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0089"
down_revision: str | None = "0088"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "objects",
    "entities",
    "places",
    "occurrences",
    "procedures",
    "collections",
    "storage_locations",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "schema_incomplete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.create_index(f"ix_{table}_schema_incomplete", table, ["schema_incomplete"])


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_schema_incomplete", table_name=table)
        op.drop_column(table, "schema_incomplete")
