# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""make portal_config site_title/site_subtitle/hero_text multilingual JSONB

These were plain strings, so a portal set up in German had no way to show an
English hero/subtitle when a visitor switched language — everything else in
portal_config (homepage_blocks, terminology) already used a {"de": ..., "en":
...} JSONB dict. Existing scalar values are wrapped as {"de": value} so
current installs keep showing what they configured.

Revision ID: 0073
Revises: 0072
Create Date: 2026-09-15
"""
from collections.abc import Sequence

from alembic import op

revision: str = '0073'
down_revision: str | None = '0072'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ('site_title', 'site_subtitle', 'hero_text')


def upgrade() -> None:
    for column in _COLUMNS:
        # Drop the old varchar server_default first — ALTER COLUMN TYPE tries to
        # cast the existing default to the new type too, and a plain string
        # default cannot be auto-cast to jsonb.
        op.alter_column('portal_config', column, server_default=None)
        op.execute(
            f"ALTER TABLE portal_config ALTER COLUMN {column} TYPE jsonb "
            f"USING CASE WHEN {column} IS NULL OR {column} = '' THEN '{{}}'::jsonb "
            f"ELSE jsonb_build_object('de', {column}) END"
        )


def downgrade() -> None:
    for column in _COLUMNS:
        op.execute(
            f"ALTER TABLE portal_config ALTER COLUMN {column} TYPE varchar "
            f"USING COALESCE({column}->>'de', (SELECT value FROM jsonb_each_text({column}) LIMIT 1), '')"
        )
