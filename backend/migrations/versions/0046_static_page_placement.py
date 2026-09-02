"""add placement to static_pages

Revision ID: 0046
Revises: c9e0f1a2b3d4
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | None = "c9e0f1a2b3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "static_pages",
        sa.Column("placement", sa.String(32), nullable=False, server_default="footer"),
    )


def downgrade() -> None:
    op.drop_column("static_pages", "placement")
