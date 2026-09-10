# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""extend role_permissions to all record types + feature_permissions table

Revision ID: 0061
Revises: 0060
Create Date: 2026-09-09
"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Default feature matrix per role (configurable through the Admin UI).
# admin/superuser always receive every feature (backend bypass), so only the
# three content roles are seeded here.
_DEFAULT_FEATURES = {
    "viewer": ["export", "sparql", "audit_log"],
    "cataloger": ["export", "sparql", "import", "working_sets", "audit_log", "vocab_terms", "manual_lock"],
    "editor": ["export", "sparql", "import", "working_sets", "audit_log", "vocab_terms", "vocab_structure", "form_variants", "storage_locations", "manual_lock"],
}
_VALID_ROLES = ("admin", "editor", "cataloger", "viewer")
_VALID_FEATURES = (
    "export", "sparql", "import", "working_sets", "audit_log",
    "vocab_terms", "vocab_structure", "schema", "subtypes", "form_variants",
    "storage_locations", "pages", "oai_sets", "banners",
    "manual_lock", "force_unlock", "users", "settings", "api_keys",
)


def upgrade() -> None:
    # --- 1. Widen role_permissions.record_type CHECK constraint ---
    op.drop_constraint("ck_role_permission_record_type", "role_permissions", type_="check")
    op.create_check_constraint(
        "ck_role_permission_record_type",
        "role_permissions",
        sa.text("record_type IN ('object', 'entity', 'place', 'occurrence', 'procedure', 'collection', 'storage_location', 'vocabulary_term')"),
    )

    # --- 2. Default record-permission seeds for the new types + viewer read + cataloger CUD removal ---
    role_permissions = sa.table(
        "role_permissions",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("role", sa.String()),
        sa.column("record_type", sa.String()),
        sa.column("action", sa.String()),
    )

    # Cataloger: delete is reserved for editor+ (concept: CRU, never delete).
    op.execute(sa.text("DELETE FROM role_permissions WHERE role = 'cataloger' AND action = 'delete'"))

    new_rows: list[dict[str, object]] = []
    # viewer: read on the 6 public types (never procedure/storage_location).
    for record_type in ("object", "entity", "place", "occurrence", "collection", "vocabulary_term"):
        new_rows.append({"id": uuid.uuid4(), "role": "viewer", "record_type": record_type, "action": "read"})
    # cataloger: collection CRU, storage_location read-only, vocabulary_term CRU.
    for action in ("create", "read", "update"):
        new_rows.append({"id": uuid.uuid4(), "role": "cataloger", "record_type": "collection", "action": action})
        new_rows.append({"id": uuid.uuid4(), "role": "cataloger", "record_type": "vocabulary_term", "action": action})
    new_rows.append({"id": uuid.uuid4(), "role": "cataloger", "record_type": "storage_location", "action": "read"})
    # editor: full CRUD on the three new types.
    for action in ("create", "read", "update", "delete"):
        for record_type in ("collection", "storage_location", "vocabulary_term"):
            new_rows.append({"id": uuid.uuid4(), "role": "editor", "record_type": record_type, "action": action})
    op.bulk_insert(role_permissions, new_rows)

    # --- 3. feature_permissions table ---
    op.create_table(
        "feature_permissions",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("feature", sa.String(length=64), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'editor', 'cataloger', 'viewer')", name="ck_feature_permission_role"),
        sa.CheckConstraint(f"feature IN ({', '.join(repr(f) for f in _VALID_FEATURES)})", name="ck_feature_permission_feature"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role", "feature", name="uq_feature_permission"),
    )
    op.create_index("ix_feature_permissions_role", "feature_permissions", ["role"])

    feature_permissions = sa.table(
        "feature_permissions",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("role", sa.String()),
        sa.column("feature", sa.String()),
    )
    op.bulk_insert(feature_permissions, [
        {"id": uuid.uuid4(), "role": role, "feature": feature}
        for role, features in _DEFAULT_FEATURES.items()
        for feature in features
    ])


def downgrade() -> None:
    op.drop_index("ix_feature_permissions_role", table_name="feature_permissions")
    op.drop_table("feature_permissions")

    op.execute(sa.text("DELETE FROM role_permissions WHERE record_type IN ('collection', 'storage_location', 'vocabulary_term')"))
    op.execute(sa.text("DELETE FROM role_permissions WHERE role = 'viewer'"))
    # Re-insert the old cataloger delete permissions to mirror migration 0033.
    role_permissions = sa.table(
        "role_permissions",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("role", sa.String()),
        sa.column("record_type", sa.String()),
        sa.column("action", sa.String()),
    )
    op.bulk_insert(role_permissions, [
        {"id": uuid.uuid4(), "role": "cataloger", "record_type": record_type, "action": action}
        for record_type in ("object", "entity", "place", "occurrence", "procedure")
        for action in ("create", "read", "update", "delete")
    ])

    op.drop_constraint("ck_role_permission_record_type", "role_permissions", type_="check")
    op.create_check_constraint(
        "ck_role_permission_record_type",
        "role_permissions",
        sa.text("record_type IN ('object', 'entity', 'place', 'occurrence', 'procedure')"),
    )