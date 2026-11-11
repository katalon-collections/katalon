# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Anonymous view/download counters plus portal download and stats switches.

Revision ID: 0087
Revises: 0086
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0087"
down_revision: str | None = "0086"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "record_usage_daily",
        sa.Column("record_type", sa.String(32), primary_key=True),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downloads", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "admin_config",
        sa.Column("usage_stats_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "portal_config",
        sa.Column("show_usage_stats", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "portal_config",
        sa.Column("media_download_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "media_download_enabled")
    op.drop_column("portal_config", "show_usage_stats")
    op.drop_column("admin_config", "usage_stats_enabled")
    op.drop_table("record_usage_daily")
