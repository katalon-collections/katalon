"""add record_subtypes and missing object/place subtype columns

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("objects", sa.Column("object_type", sa.String(length=64), nullable=True))
    op.create_index("ix_objects_object_type", "objects", ["object_type"], unique=False)

    op.add_column("places", sa.Column("place_type", sa.String(length=64), nullable=True))
    op.create_index("ix_places_place_type", "places", ["place_type"], unique=False)

    op.create_table(
        "record_subtypes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("label", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("primary_type", "name", name="uq_record_subtypes_primary_name"),
    )
    op.create_index("ix_record_subtypes_primary_type", "record_subtypes", ["primary_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_record_subtypes_primary_type", table_name="record_subtypes")
    op.drop_table("record_subtypes")

    op.drop_index("ix_places_place_type", table_name="places")
    op.drop_column("places", "place_type")

    op.drop_index("ix_objects_object_type", table_name="objects")
    op.drop_column("objects", "object_type")
