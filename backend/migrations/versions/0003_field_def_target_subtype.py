"""Add target_subtype to field_definitions

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "field_definitions",
        sa.Column("target_subtype", sa.String(64), nullable=True),
    )
    op.drop_constraint("uq_field_def_type_name", "field_definitions", type_="unique")
    op.create_index(
        "uq_field_def_type_subtype_name",
        "field_definitions",
        [sa.text("target_type"), sa.text("COALESCE(target_subtype, '')"), sa.text("name")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_field_def_type_subtype_name", "field_definitions")
    op.create_unique_constraint("uq_field_def_type_name", "field_definitions", ["target_type", "name"])
    op.drop_column("field_definitions", "target_subtype")
