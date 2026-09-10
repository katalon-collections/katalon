# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""record_subtypes: add per-subtype portal placeholder image URL

Revision ID: 0066
Revises: 0065
Create Date: 2026-09-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0066"
down_revision: str | None = "0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "record_subtypes",
        sa.Column("placeholder_image_url", sa.String(length=512), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("record_subtypes", "placeholder_image_url")
