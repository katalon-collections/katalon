"""add iiif_source_path to media_files

Revision ID: fd0b2fa1ef59
Revises: 0045
Create Date: 2026-08-30 17:19:13.840228

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'fd0b2fa1ef59'
down_revision: str | None = '0045'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('media_files', sa.Column('iiif_source_path', sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column('media_files', 'iiif_source_path')
