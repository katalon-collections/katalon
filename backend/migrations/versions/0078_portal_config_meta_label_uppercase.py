# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add meta_label_uppercase to portal_config

Revision ID: 0078
Revises: 0077
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0078"
down_revision: str | None = "0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_config",
        sa.Column(
            "meta_label_uppercase", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "meta_label_uppercase")
