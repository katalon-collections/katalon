# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""portal_config: add show_iiif_manifest_link

Lets the admin control whether the public IIIF manifest link/button appears
on the object detail page.

Revision ID: 0069
Revises: 0068
Create Date: 2026-09-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0069"
down_revision: str | None = "0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_config",
        sa.Column(
            "show_iiif_manifest_link",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "show_iiif_manifest_link")
