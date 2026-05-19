"""static_pages table

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "static_pages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("title", JSONB, nullable=False, server_default="{}"),
        sa.Column("content", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_static_pages_slug", "static_pages", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_static_pages_slug")
    op.drop_table("static_pages")
