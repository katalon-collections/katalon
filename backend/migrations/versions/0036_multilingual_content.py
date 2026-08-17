"""add multilingual content support

Revision ID: 0036
Revises: 0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "field_definitions",
        sa.Column("is_translatable", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "admin_config",
        sa.Column("supported_languages", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("admin_config", "supported_languages")
    op.drop_column("field_definitions", "is_translatable")
