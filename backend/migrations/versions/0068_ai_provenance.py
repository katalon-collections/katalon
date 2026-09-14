# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""objects/entities/places/occurrences/procedures: add ai_provenance for
field-level AI-usage disclosure

Records which field values were populated via the KI-Assistent, so admin UI
and portal can disclose AI involvement. Keyed by field path
("<field>" or "<group>.<index>.<subfield>") to {"model": str, "at": iso8601}.

Revision ID: 0068
Revises: 0067
Create Date: 2026-09-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0068"
down_revision: str | None = "0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("objects", "entities", "places", "occurrences", "procedures")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "ai_provenance",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="{}",
            ),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "ai_provenance")
