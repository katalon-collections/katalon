# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""edit_presence: soft presence lock + admin_config.presence_lock_mode

Revision ID: 0060
Revises: 0059
Create Date: 2026-09-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "edit_presence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("resource_type", "resource_id", "session_id", name="uq_edit_presence_session"),
    )
    op.create_index("ix_edit_presence_resource", "edit_presence", ["resource_type", "resource_id"])
    op.add_column(
        "admin_config",
        sa.Column("presence_lock_mode", sa.String(16), nullable=False, server_default="warning"),
    )


def downgrade() -> None:
    op.drop_column("admin_config", "presence_lock_mode")
    op.drop_index("ix_edit_presence_resource", table_name="edit_presence")
    op.drop_table("edit_presence")
