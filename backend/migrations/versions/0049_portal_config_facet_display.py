"""add facet_sort and facet_initial_count to portal_config

Revision ID: 0049
Revises: 0048
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_config",
        sa.Column("facet_sort", sa.String(16), nullable=False, server_default="count"),
    )
    op.add_column(
        "portal_config",
        sa.Column("facet_initial_count", sa.Integer(), nullable=False, server_default="10"),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "facet_initial_count")
    op.drop_column("portal_config", "facet_sort")
