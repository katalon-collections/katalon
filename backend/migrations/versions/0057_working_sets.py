# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""working_sets: Arbeitslisten / Sets für Ad-hoc-Gruppierungen von Datensätzen

Revision ID: 0057
Revises: 0056
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "working_sets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_working_sets_user_id", "working_sets", ["user_id"])
    op.create_index("ix_working_sets_record_type", "working_sets", ["record_type"])

    op.create_table(
        "working_set_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "set_id",
            UUID(as_uuid=True),
            sa.ForeignKey("working_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("record_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("set_id", "record_id", name="uq_working_set_items_set_record"),
    )
    op.create_index("ix_working_set_items_set_id", "working_set_items", ["set_id"])
    op.create_index("ix_working_set_items_record_id", "working_set_items", ["record_id"])


def downgrade() -> None:
    op.drop_index("ix_working_set_items_record_id", table_name="working_set_items")
    op.drop_index("ix_working_set_items_set_id", table_name="working_set_items")
    op.drop_table("working_set_items")

    op.drop_index("ix_working_sets_record_type", table_name="working_sets")
    op.drop_index("ix_working_sets_user_id", table_name="working_sets")
    op.drop_table("working_sets")
