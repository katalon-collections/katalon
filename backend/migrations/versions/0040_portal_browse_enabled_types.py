"""add portal browsing type configuration

Revision ID: 0040
Revises: 0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portal_config",
        sa.Column(
            "browse_enabled_types",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"object\", \"entity\", \"place\", \"occurrence\"]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("portal_config", "browse_enabled_types")
