# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""drop status from storage_locations, make idno required

Revision ID: 0055
Revises: 0054
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_storage_locations_status", table_name="storage_locations")
    op.drop_column("storage_locations", "status")
    op.alter_column("storage_locations", "idno", existing_type=sa.String(length=128), nullable=False)


def downgrade() -> None:
    op.alter_column("storage_locations", "idno", existing_type=sa.String(length=128), nullable=True)
    op.add_column(
        "storage_locations",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
    )
    op.create_index("ix_storage_locations_status", "storage_locations", ["status"])
