"""add facet_fields to portal_config

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portal_config",
        sa.Column("facet_fields", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "facet_fields")
