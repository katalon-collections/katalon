# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""resource_locks: manual exclusive lock table

Revision ID: 0062
Revises: 0061
Create Date: 2026-09-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_locks",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "locked_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("locked_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("reason", sa.String(length=256), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_type", "resource_id", name="uq_resource_lock"),
    )
    op.create_index("ix_resource_locks_resource_type", "resource_locks", ["resource_type"])
    op.create_index("ix_resource_locks_resource_id", "resource_locks", ["resource_id"])
    op.create_index("ix_resource_locks_locked_by", "resource_locks", ["locked_by"])
    op.create_index("ix_resource_locks_expires_at", "resource_locks", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_resource_locks_expires_at", table_name="resource_locks")
    op.drop_index("ix_resource_locks_locked_by", table_name="resource_locks")
    op.drop_index("ix_resource_locks_resource_id", table_name="resource_locks")
    op.drop_index("ix_resource_locks_resource_type", table_name="resource_locks")
    op.drop_table("resource_locks")
