"""add onboarding_completed_at to users

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed_at")
