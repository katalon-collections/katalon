"""add configurable record permissions

Revision ID: 0033
Revises: 0032
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RECORD_TYPES = ("object", "entity", "place", "occurrence", "procedure")
_ACTIONS = ("read", "create", "update", "delete")


def upgrade() -> None:
    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'editor', 'cataloger', 'viewer')", name="ck_role_permission_role"),
        sa.CheckConstraint("record_type IN ('object', 'entity', 'place', 'occurrence', 'procedure')", name="ck_role_permission_record_type"),
        sa.CheckConstraint("action IN ('read', 'create', 'update', 'delete')", name="ck_role_permission_action"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role", "record_type", "action", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_role", "role_permissions", ["role"])
    op.create_index("ix_role_permissions_record_type", "role_permissions", ["record_type"])
    op.bulk_insert(
        sa.table("role_permissions", sa.column("id", postgresql.UUID(as_uuid=True)), sa.column("role", sa.String()),
                 sa.column("record_type", sa.String()), sa.column("action", sa.String())),
        [{"id": uuid.uuid4(), "role": role, "record_type": record_type, "action": action}
        for role in ("editor", "cataloger")
         for record_type in _RECORD_TYPES for action in _ACTIONS],
    )


def downgrade() -> None:
    op.drop_index("ix_role_permissions_record_type", table_name="role_permissions")
    op.drop_index("ix_role_permissions_role", table_name="role_permissions")
    op.drop_table("role_permissions")
