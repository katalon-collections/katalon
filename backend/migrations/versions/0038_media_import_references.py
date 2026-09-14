"""add durable media import references

Revision ID: 0038
Revises: 0037
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_import_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("normalized_filename", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "object_id",
            "normalized_filename",
            name="uq_media_import_references_object_filename",
        ),
    )
    op.create_index(
        "ix_media_import_references_object_id",
        "media_import_references",
        ["object_id"],
    )
    op.create_index(
        "ix_media_import_references_normalized_filename",
        "media_import_references",
        ["normalized_filename"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_media_import_references_normalized_filename",
        table_name="media_import_references",
    )
    op.drop_index(
        "ix_media_import_references_object_id",
        table_name="media_import_references",
    )
    op.drop_table("media_import_references")
