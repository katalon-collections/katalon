"""add is_facet to field_definitions

Revision ID: 5c8e9a2b3f41
Revises: 4ad5067d1e60
Create Date: 2026-05-19 22:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '5c8e9a2b3f41'
down_revision: str | None = '4ad5067d1e60'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'field_definitions',
        sa.Column('is_facet', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('field_definitions', 'is_facet')
