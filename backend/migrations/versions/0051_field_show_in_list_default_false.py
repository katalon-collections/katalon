"""field definitions default show_in_list to false

Revision ID: 0051
Revises: 0050
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("field_definitions", "show_in_list", server_default=sa.false())


def downgrade() -> None:
    op.alter_column("field_definitions", "show_in_list", server_default=sa.true())
