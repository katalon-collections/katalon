"""Add rights metadata to media files.

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("media_files", sa.Column("license_uri", sa.String(512), nullable=True))
    op.add_column("media_files", sa.Column("rights_holder", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("media_files", "rights_holder")
    op.drop_column("media_files", "license_uri")
