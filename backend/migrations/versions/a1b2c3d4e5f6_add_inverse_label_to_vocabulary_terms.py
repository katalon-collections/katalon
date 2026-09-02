"""add inverse_label to vocabulary_terms

Revision ID: a1b2c3d4e5f6
Revises: 5c8e9a2b3f41
Create Date: 2026-06-18 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '0021'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'vocabulary_terms',
        sa.Column('inverse_label', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    )


def downgrade() -> None:
    op.drop_column('vocabulary_terms', 'inverse_label')
