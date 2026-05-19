"""convert facet_fields from list to per-type dict

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPES = ("object", "entity", "place", "occurrence")


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT key, facet_fields FROM portal_config")
    ).fetchall()
    for key, old in rows:
        if isinstance(old, list):
            new = {t: (old if t == "object" else []) for t in TYPES}
        elif isinstance(old, dict):
            new = old  # already migrated
        else:
            new = {t: [] for t in TYPES}
        import json
        conn.execute(
            sa.text(f"UPDATE portal_config SET facet_fields = '{json.dumps(new)}'::jsonb WHERE key = '{key}'"),
        )


def downgrade() -> None:
    import json
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT key, facet_fields FROM portal_config")
    ).fetchall()
    for key, val in rows:
        old = val.get("object", []) if isinstance(val, dict) else []
        conn.execute(
            sa.text(f"UPDATE portal_config SET facet_fields = '{json.dumps(old)}'::jsonb WHERE key = '{key}'"),
        )
