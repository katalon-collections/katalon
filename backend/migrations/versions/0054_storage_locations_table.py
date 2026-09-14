# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""create storage_locations table

Revision ID: 0054
Revises: 0053
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "storage_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("idno", sa.String(length=128), nullable=True),
        sa.Column("storage_location_type", sa.String(length=64), nullable=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("storage_locations.id", ondelete="SET NULL"),
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
    op.create_index("ix_storage_locations_idno", "storage_locations", ["idno"], unique=True)
    op.create_index(
        "ix_storage_locations_storage_location_type", "storage_locations", ["storage_location_type"]
    )
    op.create_index("ix_storage_locations_parent_id", "storage_locations", ["parent_id"])
    op.create_index("ix_storage_locations_status", "storage_locations", ["status"])
    op.create_index("ix_storage_locations_deleted_at", "storage_locations", ["deleted_at"])
    op.create_index(
        "ix_storage_locations_metadata_gin",
        "storage_locations",
        ["metadata"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_storage_locations_metadata_gin", table_name="storage_locations", postgresql_using="gin"
    )
    op.drop_index("ix_storage_locations_deleted_at", table_name="storage_locations")
    op.drop_index("ix_storage_locations_status", table_name="storage_locations")
    op.drop_index("ix_storage_locations_parent_id", table_name="storage_locations")
    op.drop_index("ix_storage_locations_storage_location_type", table_name="storage_locations")
    op.drop_index("ix_storage_locations_idno", table_name="storage_locations")
    op.drop_table("storage_locations")
