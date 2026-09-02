"""add media rights defaults

Revision ID: 0031
Revises: 0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("admin_config", sa.Column("media_default_license_uri", sa.String(length=512), nullable=True))
    op.add_column("admin_config", sa.Column("media_default_rights_holder", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_config", "media_default_rights_holder")
    op.drop_column("admin_config", "media_default_license_uri")
