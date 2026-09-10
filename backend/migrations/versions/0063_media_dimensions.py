# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""media_files: add width/height, backfill from iiif_manifest

Revision ID: 0063
Revises: 0062
Create Date: 2026-09-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("media_files", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("media_files", sa.Column("height", sa.Integer(), nullable=True))
    # Backfill dimensions already recorded in the per-file IIIF manifest
    # (canvas width/height at items -> 0).
    op.execute(
        """
        UPDATE media_files
        SET width = (iiif_manifest -> 'items' -> 0 ->> 'width')::int,
            height = (iiif_manifest -> 'items' -> 0 ->> 'height')::int
        WHERE width IS NULL
          AND iiif_manifest -> 'items' -> 0 ->> 'width' ~ '^\\d+$'
          AND iiif_manifest -> 'items' -> 0 ->> 'height' ~ '^\\d+$'
        """
    )


def downgrade() -> None:
    op.drop_column("media_files", "height")
    op.drop_column("media_files", "width")
