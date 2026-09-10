"""add metadata_formats table for pluggable export format registry

Registers metadata export formats (OAI-DC, LIDO, METS/MODS built in) the
same way authority_sources registers authority adapters: a row here either
patches config onto a built-in format (same id) or points adapter_class at
a custom implementation (new id). No is_enabled column — presence of a row
plus the format's own mappings gate visibility.

Revision ID: 0045
Revises: 0044
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metadata_formats",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("adapter_class", sa.String(256), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("metadata_formats")
