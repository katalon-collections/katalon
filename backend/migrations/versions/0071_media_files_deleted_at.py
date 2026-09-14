# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""media_files: add deleted_at as a committed deletion-intent marker

Fixes the rollback-unsafe media delete path (#390): both the manual delete
endpoint and the automatic purge worker used to remove the physical file
before the database row, so a later DB failure left a PostgreSQL rollback
next to an already-gone original. `deleted_at` lets the deletion intent be
recorded and committed first; physical storage deletion becomes a separate,
idempotent, retryable step (katalon.services.media_deletion_service) that
only ever runs against a row whose intent is already durable. A row with
`deleted_at` set but still present means "physical cleanup pending/retry
needed" — it is never a silently successful or silently lost deletion.

Revision ID: 0071
Revises: 0070
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0071"
down_revision: str | None = "0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("media_files", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_media_files_deleted_at", "media_files", ["deleted_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_media_files_deleted_at", table_name="media_files")
    op.drop_column("media_files", "deleted_at")
