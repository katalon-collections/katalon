"""portal_config table

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_config",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("site_title", sa.String(256), nullable=False, server_default="Katalon"),
        sa.Column("site_subtitle", sa.String(512), nullable=False, server_default=""),
        sa.Column("hero_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("featured_object_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("accent_color", sa.String(32), nullable=False, server_default="#1e3a8a"),
        sa.Column("logo_url", sa.String(512), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Seed the default row
    op.execute(
        "INSERT INTO portal_config (key) VALUES ('default') ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("portal_config")
