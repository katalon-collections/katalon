# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add media_files.credit_line and record_subtypes.concept_alternatives

Revision ID: 0082
Revises: 0081
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0082"
down_revision: str | None = "0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("media_files", sa.Column("credit_line", sa.Text(), nullable=True))
    op.add_column(
        "record_subtypes",
        sa.Column(
            "concept_alternatives",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("record_subtypes", "concept_alternatives")
    op.drop_column("media_files", "credit_line")
