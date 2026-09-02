"""field_definitions: add show_in_detail flag

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "field_definitions",
        sa.Column("show_in_detail", sa.Boolean, nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("field_definitions", "show_in_detail")
