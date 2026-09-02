"""drop unused search_vector columns

Search runs entirely through Elasticsearch; these TSVECTOR columns were
never populated by app code (dead leftover from before the ES decision).

Revision ID: 0044
Revises: 0043
Create Date: 2026-08-27
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ["objects", "entities", "places", "occurrences", "procedures"]


def upgrade() -> None:
    op.drop_index("ix_objects_search_vector", table_name="objects")
    for table in TABLES:
        op.drop_column(table, "search_vector")


def downgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("search_vector", postgresql.TSVECTOR, nullable=True))
    op.create_index("ix_objects_search_vector", "objects", ["search_vector"], postgresql_using="gin")
