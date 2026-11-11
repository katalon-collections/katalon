# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Add places.parent_id for place hierarchies (Land > Region > Ort).

Revision ID: 0086
Revises: 0085
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0086"
down_revision: str | None = "0085"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "places",
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("places.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_places_parent_id", "places", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_places_parent_id", table_name="places")
    op.drop_column("places", "parent_id")
