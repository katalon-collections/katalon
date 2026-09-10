"""add procedures

Revision ID: 0022
Revises: a1b2c3d4e5f6
Create Date: 2026-06-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "objects",
        sa.Column("collection_status", sa.String(32), nullable=False, server_default="active"),
    )
    op.create_index("ix_objects_collection_status", "objects", ["collection_status"])

    op.create_table(
        "procedures",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idno", sa.String(128), nullable=True),
        sa.Column("procedure_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("reference_number", sa.String(128), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_procedures_idno", "procedures", ["idno"], unique=True)
    op.create_index("ix_procedures_procedure_type", "procedures", ["procedure_type"])
    op.create_index("ix_procedures_status", "procedures", ["status"])
    op.create_index("ix_procedures_start_date", "procedures", ["start_date"])
    op.create_index("ix_procedures_end_date", "procedures", ["end_date"])
    op.create_index("ix_procedures_due_date", "procedures", ["due_date"])
    op.create_index("ix_procedures_reference_number", "procedures", ["reference_number"])
    op.create_index("ix_procedures_metadata_gin", "procedures", ["metadata"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_procedures_metadata_gin", table_name="procedures")
    op.drop_index("ix_procedures_reference_number", table_name="procedures")
    op.drop_index("ix_procedures_due_date", table_name="procedures")
    op.drop_index("ix_procedures_end_date", table_name="procedures")
    op.drop_index("ix_procedures_start_date", table_name="procedures")
    op.drop_index("ix_procedures_status", table_name="procedures")
    op.drop_index("ix_procedures_procedure_type", table_name="procedures")
    op.drop_index("ix_procedures_idno", table_name="procedures")
    op.drop_table("procedures")
    op.drop_index("ix_objects_collection_status", table_name="objects")
    op.drop_column("objects", "collection_status")
