# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add auto_purge_enabled/purge_retention_days to admin_config (#414)

Revision ID: 0076
Revises: 0075
Create Date: 2026-09-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0076"
down_revision: str | None = "0075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "admin_config",
        sa.Column("auto_purge_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "admin_config",
        sa.Column("purge_retention_days", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    op.drop_column("admin_config", "purge_retention_days")
    op.drop_column("admin_config", "auto_purge_enabled")
