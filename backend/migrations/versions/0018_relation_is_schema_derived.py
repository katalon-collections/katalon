"""add is_schema_derived to relations

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "relations",
        sa.Column("is_schema_derived", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("relations", "is_schema_derived")
