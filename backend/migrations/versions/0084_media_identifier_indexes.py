# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Index both identifiers used by the IIIF authorization lookup.

Revision ID: 0084
Revises: 0083
"""

from alembic import op
from sqlalchemy import text

revision: str = "0084"
down_revision: str | None = "0083"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Concurrent builds keep media writes available while indexing existing rows.
    context = op.get_context()
    with context.autocommit_block():
        for column in ("storage_key", "iiif_storage_key"):
            name = f"ix_media_files_{column}"
            if not context.as_sql:
                valid = op.get_bind().scalar(
                    text("SELECT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:name)"),
                    {"name": name},
                )
                # An interrupted concurrent build leaves an index IF NOT EXISTS would skip.
                if valid is False:
                    op.drop_index(name, table_name="media_files", postgresql_concurrently=True)
            op.create_index(
                name, "media_files", [column],
                postgresql_concurrently=True, if_not_exists=True,
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_media_files_iiif_storage_key", table_name="media_files",
            postgresql_concurrently=True, if_exists=True,
        )
        op.drop_index(
            "ix_media_files_storage_key", table_name="media_files",
            postgresql_concurrently=True, if_exists=True,
        )
