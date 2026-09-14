# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""field_definitions: clear stale show_in_list on sub-fields

Sub-fields (parent_id set) are embedded as `children` on their group field
and are never returned by the top-level schema.list() query the record list
view reads from (schema_admin.list_fields filters parent_id IS NULL) —
show_in_list has never had any effect on them. Some rows still carry a
stale `show_in_list = true` from before the API started rejecting it
(schema_admin.create_field/update_field now force it false for parent_id
rows). Clear the dead flag so the schema admin UI stops showing a setting
that never worked and never will.

Revision ID: 0070
Revises: 0069
Create Date: 2026-09-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0070"
down_revision: str | None = "0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    field_definitions = sa.table(
        "field_definitions",
        sa.column("parent_id"),
        sa.column("show_in_list"),
    )
    op.execute(
        field_definitions.update()
        .where(field_definitions.c.parent_id.isnot(None))
        .where(field_definitions.c.show_in_list.is_(True))
        .values(show_in_list=False)
    )


def downgrade() -> None:
    # Irreversible data cleanup — the stale flag never had any observable effect,
    # so there is nothing meaningful to restore.
    pass
