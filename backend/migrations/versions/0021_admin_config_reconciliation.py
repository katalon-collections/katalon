"""add reconciliation settings to admin_config

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-06
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("admin_config", sa.Column("reconciliation_enabled", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("admin_config", sa.Column("reconciliation_threshold", sa.Integer(), server_default="5", nullable=False))
    op.add_column("admin_config", sa.Column("reconciliation_id_diff_enabled", sa.Boolean(), server_default="true", nullable=False))


def downgrade() -> None:
    op.drop_column("admin_config", "reconciliation_id_diff_enabled")
    op.drop_column("admin_config", "reconciliation_threshold")
    op.drop_column("admin_config", "reconciliation_enabled")
