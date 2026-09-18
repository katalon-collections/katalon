# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add concept normdaten fields to record_subtypes

Revision ID: 0075
Revises: 0074
Create Date: 2026-09-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0075"
down_revision: str | None = "0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("record_subtypes", sa.Column("concept_source", sa.String(length=32), nullable=True))
    op.add_column("record_subtypes", sa.Column("concept_id", sa.String(length=64), nullable=True))
    op.add_column("record_subtypes", sa.Column("concept_uri", sa.String(length=512), nullable=True))
    op.add_column("record_subtypes", sa.Column("concept_label", sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column("record_subtypes", "concept_label")
    op.drop_column("record_subtypes", "concept_uri")
    op.drop_column("record_subtypes", "concept_id")
    op.drop_column("record_subtypes", "concept_source")
