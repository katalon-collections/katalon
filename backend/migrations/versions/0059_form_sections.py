# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""form_sections: Configurable tab sections for record forms

Revision ID: 0059
Revises: 0058
Create Date: 2026-09-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "form_sections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_subtype", sa.String(64), nullable=True),
        sa.Column("label", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("field_names", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_form_sections_target_type", "form_sections", ["target_type"])


def downgrade() -> None:
    op.drop_index("ix_form_sections_target_type", table_name="form_sections")
    op.drop_table("form_sections")
