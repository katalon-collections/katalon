"""add idno to entities places occurrences

Revision ID: 56b592d317dd
Revises: 0007
Create Date: 2026-05-04 13:32:47.156299

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '56b592d317dd'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('entities', sa.Column('idno', sa.String(128), nullable=True))
    op.create_index('ix_entities_idno', 'entities', ['idno'], unique=True)
    op.add_column('places', sa.Column('idno', sa.String(128), nullable=True))
    op.create_index('ix_places_idno', 'places', ['idno'], unique=True)
    op.add_column('occurrences', sa.Column('idno', sa.String(128), nullable=True))
    op.create_index('ix_occurrences_idno', 'occurrences', ['idno'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_occurrences_idno', table_name='occurrences')
    op.drop_column('occurrences', 'idno')
    op.drop_index('ix_places_idno', table_name='places')
    op.drop_column('places', 'idno')
    op.drop_index('ix_entities_idno', table_name='entities')
    op.drop_column('entities', 'idno')
