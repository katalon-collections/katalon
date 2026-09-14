"""add parent_id to field_definitions (container fields)

Revision ID: 0019
Revises: 5c8e9a2b3f41
Create Date: 2026-05-25

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0019"
down_revision: str | None = "5c8e9a2b3f41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "field_definitions",
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("field_definitions.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_field_defs_parent_id", "field_definitions", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_field_defs_parent_id", "field_definitions")
    op.drop_column("field_definitions", "parent_id")
