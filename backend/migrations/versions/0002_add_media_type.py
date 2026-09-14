"""Add media_type column to media_files

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-01

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("media_files", sa.Column("media_type", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("media_files", "media_type")
