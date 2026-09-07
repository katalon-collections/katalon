# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""saved_sparql_queries: Gespeicherte SPARQL-Abfragen für den Query Builder

Revision ID: 0056
Revises: 0055
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_sparql_queries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_saved_sparql_queries_title", "saved_sparql_queries", ["title"])
    op.create_index("ix_saved_sparql_queries_created_by", "saved_sparql_queries", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_saved_sparql_queries_created_by", table_name="saved_sparql_queries")
    op.drop_index("ix_saved_sparql_queries_title", table_name="saved_sparql_queries")
    op.drop_table("saved_sparql_queries")
