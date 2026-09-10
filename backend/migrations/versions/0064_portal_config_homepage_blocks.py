# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""portal_config: add homepage_blocks, seed default blocks from featured_object_ids

Revision ID: 0064
Revises: 0063
Create Date: 2026-09-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_BLOCKS = """
[
  {"id": "curated", "type": "curated", "enabled": true,
   "title": {"de": "Ausgewählte Objekte", "en": "Featured Objects"}},
  {"id": "objects", "type": "objects", "enabled": true, "limit": 12,
   "title": {"de": "Neueste Objekte", "en": "Recent Objects"}}
]
"""


def upgrade() -> None:
    op.add_column(
        "portal_config",
        sa.Column("homepage_blocks", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    # Existing installs keep their current homepage look (curated + recent)
    # instead of going blank after upgrade.
    op.execute(
        sa.text("UPDATE portal_config SET homepage_blocks = CAST(:blocks AS jsonb)").bindparams(
            blocks=_DEFAULT_BLOCKS
        )
    )


def downgrade() -> None:
    op.drop_column("portal_config", "homepage_blocks")
