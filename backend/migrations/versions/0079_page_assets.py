# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add page_assets table

Revision ID: 0079
Revises: 0078
Create Date: 2026-10-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0079"
down_revision: str | None = "0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page_assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "page_id",
            UUID(as_uuid=True),
            sa.ForeignKey("static_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_page_assets_page_id", "page_assets", ["page_id"])


def downgrade() -> None:
    op.drop_index("ix_page_assets_page_id")
    op.drop_table("page_assets")
