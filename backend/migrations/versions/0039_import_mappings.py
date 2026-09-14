"""add import mappings

Revision ID: 0039
Revises: 0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("subtype", sa.String(length=64), nullable=True),
        sa.Column("media_selector", sa.String(length=512), nullable=True),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_import_mappings_record_type",
        "import_mappings",
        ["record_type"],
    )
    op.create_index(
        "ix_import_mappings_created_by",
        "import_mappings",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_import_mappings_created_by", table_name="import_mappings")
    op.drop_index("ix_import_mappings_record_type", table_name="import_mappings")
    op.drop_table("import_mappings")
