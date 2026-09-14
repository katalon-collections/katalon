"""replace absolute media paths with relative storage keys

Revision ID: c9e0f1a2b3d4
Revises: fd0b2fa1ef59
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from katalon.core.media_storage import relative_storage_key, storage_path

revision: str = "c9e0f1a2b3d4"
down_revision: str | None = "fd0b2fa1ef59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("media_files", "file_path", new_column_name="storage_key")
    op.alter_column("media_files", "iiif_source_path", new_column_name="iiif_storage_key")
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, storage_key, iiif_storage_key FROM media_files")).mappings()
    for row in rows:
        storage_key = relative_storage_key(row["storage_key"])
        iiif_storage_key = (
            relative_storage_key(row["iiif_storage_key"]) if row["iiif_storage_key"] else None
        )
        bind.execute(
            sa.text(
                "UPDATE media_files SET storage_key = :storage_key, "
                "iiif_storage_key = :iiif_storage_key WHERE id = :id"
            ),
            {"id": row["id"], "storage_key": storage_key, "iiif_storage_key": iiif_storage_key},
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, storage_key, iiif_storage_key FROM media_files")).mappings()
    for row in rows:
        bind.execute(
            sa.text("UPDATE media_files SET storage_key = :storage_key, iiif_storage_key = :iiif_storage_key WHERE id = :id"),
            {
                "id": row["id"],
                "storage_key": str(storage_path(row["storage_key"])),
                "iiif_storage_key": str(storage_path(row["iiif_storage_key"])) if row["iiif_storage_key"] else None,
            },
        )
    op.alter_column("media_files", "iiif_storage_key", new_column_name="iiif_source_path")
    op.alter_column("media_files", "storage_key", new_column_name="file_path")
