# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add footer, notice and header/hero logo options to portal_config

Revision ID: 0081
Revises: 0080
Create Date: 2026-10-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0081"
down_revision: str | None = "0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("footer", "notice"):
        op.add_column(
            "portal_config",
            sa.Column(
                column,
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    op.add_column(
        "portal_config",
        sa.Column("header_show_title", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "portal_config",
        sa.Column("hero_hide_title", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "hero_hide_title")
    op.drop_column("portal_config", "header_show_title")
    op.drop_column("portal_config", "notice")
    op.drop_column("portal_config", "footer")
