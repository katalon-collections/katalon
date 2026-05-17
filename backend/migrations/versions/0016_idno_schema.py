"""add admin_config and idno_counters tables

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_config",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("idno_schemas", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("idno_patterns", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "idno_counters",
        sa.Column("record_type", sa.String(32), primary_key=True),
        sa.Column("current_value", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("idno_counters")
    op.drop_table("admin_config")
