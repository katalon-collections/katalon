"""portal_config: add color_tokens JSONB column

Revision ID: 0008
Revises: 56b592d317dd
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "56b592d317dd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portal_config",
        sa.Column("color_tokens", JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "color_tokens")
