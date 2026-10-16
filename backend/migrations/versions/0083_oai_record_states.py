# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add oai_record_states for OAI-PMH deleted records

Revision ID: 0083
Revises: 0082
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0083"
down_revision: str | None = "0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Record types OAI-PMH can disseminate (storage locations and procedures never).
_TABLES = {
    "object": "objects",
    "entity": "entities",
    "place": "places",
    "occurrence": "occurrences",
    "collection": "collections",
}


def upgrade() -> None:
    op.create_table(
        "oai_record_states",
        sa.Column("record_type", sa.String(32), primary_key=True),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_oai_record_states_deleted_at", "oai_record_states", ["deleted_at"])
    # Everything public today counts as disseminated; earlier removals are unknown.
    for record_type, table in _TABLES.items():
        op.execute(
            sa.text(
                f"INSERT INTO oai_record_states (record_type, record_id) "  # noqa: S608
                f"SELECT :record_type, id FROM {table} "
                "WHERE status IN ('public', 'published') AND deleted_at IS NULL"
            ).bindparams(record_type=record_type)
        )


def downgrade() -> None:
    op.drop_index("ix_oai_record_states_deleted_at", table_name="oai_record_states")
    op.drop_table("oai_record_states")
