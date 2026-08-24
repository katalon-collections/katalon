"""configurable portal detail page layout

Revision ID: 0043
Revises: 0042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "field_definitions",
        sa.Column("detail_slot", sa.String(length=16), nullable=False, server_default="sidebar"),
    )
    op.add_column(
        "field_definitions",
        sa.Column("detail_role", sa.String(length=16), nullable=False, server_default="none"),
    )
    op.add_column(
        "portal_config",
        sa.Column(
            "detail_sidebar_position", sa.String(length=16), nullable=False, server_default="right"
        ),
    )

    field_definitions = sa.table(
        "field_definitions",
        sa.column("name", sa.String),
        sa.column("detail_slot", sa.String),
        sa.column("detail_role", sa.String),
    )
    op.execute(
        field_definitions.update()
        .where(field_definitions.c.name.in_(("description", "keywords")))
        .values(detail_slot="main")
    )
    op.execute(
        field_definitions.update()
        .where(field_definitions.c.name == "description")
        .values(detail_role="description")
    )


def downgrade() -> None:
    op.drop_column("portal_config", "detail_sidebar_position")
    op.drop_column("field_definitions", "detail_role")
    op.drop_column("field_definitions", "detail_slot")
