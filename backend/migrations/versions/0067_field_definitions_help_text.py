# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""field_definitions: add per-field help text (i18n) for data entry forms

Revision ID: 0067
Revises: 0066
Create Date: 2026-09-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "field_definitions",
        sa.Column("help_text", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("field_definitions", "help_text")
