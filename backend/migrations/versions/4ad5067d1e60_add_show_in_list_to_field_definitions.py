"""add show_in_list to field_definitions

Revision ID: 4ad5067d1e60
Revises: 0018
Create Date: 2026-05-19 22:04:20.581096

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '4ad5067d1e60'
down_revision: str | None = '0018'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'field_definitions',
        sa.Column('show_in_list', sa.Boolean(), server_default='true', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('field_definitions', 'show_in_list')
