"""oai_sets: konfigurierbare OAI-PMH-Sets auf Basis von Suchanfragen

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-06
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oai_sets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("set_spec", sa.String(128), nullable=False, unique=True),
        sa.Column("set_name", sa.String(256), nullable=False),
        sa.Column("filter_record_type", sa.String(32), nullable=True),
        sa.Column("filter_q", sa.Text, nullable=True),
        sa.Column("filter_status", sa.String(32), nullable=True),
        sa.Column("filter_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_oai_sets_set_spec", "oai_sets", ["set_spec"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_oai_sets_set_spec", table_name="oai_sets")
    op.drop_table("oai_sets")
