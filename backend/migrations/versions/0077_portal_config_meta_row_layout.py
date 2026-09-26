# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add meta_row_layout to portal_config

Revision ID: 0077
Revises: 0076
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0077"
down_revision: str | None = "0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_config",
        sa.Column(
            "meta_row_layout", sa.String(length=16), nullable=False, server_default="stacked"
        ),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "meta_row_layout")
