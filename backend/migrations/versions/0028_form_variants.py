"""add form_variants and form_variant_role_defaults tables

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "form_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_subtype", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("label", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("field_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("is_default_global", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_form_variants_target_type", "form_variants", ["target_type"], unique=False)

    op.create_table(
        "form_variant_role_defaults",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_subtype", sa.String(length=64), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["variant_id"], ["form_variants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "target_type", "target_subtype", "role",
            name="uq_form_variant_role_defaults_scope_role",
        ),
    )
    op.create_index(
        "ix_form_variant_role_defaults_variant_id",
        "form_variant_role_defaults",
        ["variant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_form_variant_role_defaults_variant_id", table_name="form_variant_role_defaults")
    op.drop_table("form_variant_role_defaults")

    op.drop_index("ix_form_variants_target_type", table_name="form_variants")
    op.drop_table("form_variants")
