"""add metadata mappings

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metadata_mappings",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("field_definition_id", UUID(as_uuid=True), nullable=False),
        sa.Column("format_key", sa.String(length=64), nullable=False),
        sa.Column("target_path", sa.String(length=256), nullable=False),
        sa.Column("settings", JSONB(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["field_definition_id"], ["field_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "field_definition_id",
            "format_key",
            "target_path",
            name="uq_metadata_mappings_field_format_target",
        ),
    )
    op.create_index("ix_metadata_mappings_field_definition_id", "metadata_mappings", ["field_definition_id"])
    op.create_index("ix_metadata_mappings_format_key", "metadata_mappings", ["format_key"])
    op.create_index(
        "ix_metadata_mappings_format_enabled",
        "metadata_mappings",
        ["format_key", "is_enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_metadata_mappings_format_enabled", table_name="metadata_mappings")
    op.drop_index("ix_metadata_mappings_format_key", table_name="metadata_mappings")
    op.drop_index("ix_metadata_mappings_field_definition_id", table_name="metadata_mappings")
    op.drop_table("metadata_mappings")
