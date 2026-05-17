"""add is_searchable to field_definitions

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "field_definitions",
        sa.Column("is_searchable", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("field_definitions", "is_searchable")
