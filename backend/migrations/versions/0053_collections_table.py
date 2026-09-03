# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""create collections table

Revision ID: 0053
Revises: 0052
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idno", sa.String(length=128), nullable=True),
        sa.Column("collection_type", sa.String(length=64), nullable=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_collections_idno", "collections", ["idno"], unique=True)
    op.create_index("ix_collections_collection_type", "collections", ["collection_type"])
    op.create_index("ix_collections_parent_id", "collections", ["parent_id"])
    op.create_index("ix_collections_status", "collections", ["status"])
    op.create_index("ix_collections_deleted_at", "collections", ["deleted_at"])
    op.create_index(
        "ix_collections_metadata_gin",
        "collections",
        ["metadata"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_collections_metadata_gin", table_name="collections", postgresql_using="gin")
    op.drop_index("ix_collections_deleted_at", table_name="collections")
    op.drop_index("ix_collections_status", table_name="collections")
    op.drop_index("ix_collections_parent_id", table_name="collections")
    op.drop_index("ix_collections_collection_type", table_name="collections")
    op.drop_index("ix_collections_idno", table_name="collections")
    op.drop_table("collections")
