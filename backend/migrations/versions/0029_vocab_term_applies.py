"""add applies_from/applies_to to vocabulary_terms

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vocabulary_terms",
        sa.Column(
            "applies_from",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "vocabulary_terms",
        sa.Column(
            "applies_to",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("vocabulary_terms", "applies_to")
    op.drop_column("vocabulary_terms", "applies_from")
