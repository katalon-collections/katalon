"""portal_config: add placeholder_image_url column

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "portal_config",
        sa.Column("placeholder_image_url", sa.String(512), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "placeholder_image_url")
