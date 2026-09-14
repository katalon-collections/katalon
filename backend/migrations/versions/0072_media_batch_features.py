# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add media/batch features, seed cataloger+editor for parity with manage_content

Media uploads/edits and batch operations used to be gated by the coarse
`manage_content` capability (cataloger/editor/admin/superuser). #389 replaces
that with the configurable `media`/`batch` feature-permission gate plus
per-record-type write permission, matching export/import/working_sets. This
migration widens the `feature_permissions.feature` CHECK constraint to admit
the two new values and seeds cataloger/editor with both so existing installs
keep their current effective access after the upgrade — an admin can still
revoke either via the Admin UI matrix afterward.

Revision ID: 0072
Revises: 0071
Create Date: 2026-09-13
"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0072"
down_revision: str | None = "0071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_FEATURES = ("media", "batch")
_VALID_FEATURES = (
    "export", "sparql", "import", "working_sets", "audit_log",
    "vocab_terms", "vocab_structure", "schema", "subtypes", "form_variants",
    "storage_locations", "pages", "oai_sets", "banners",
    "manual_lock", "force_unlock", "users", "settings", "api_keys",
    *_NEW_FEATURES,
)


def upgrade() -> None:
    op.drop_constraint("ck_feature_permission_feature", "feature_permissions", type_="check")
    op.create_check_constraint(
        "ck_feature_permission_feature",
        "feature_permissions",
        sa.text(f"feature IN ({', '.join(repr(f) for f in _VALID_FEATURES)})"),
    )

    feature_permissions = sa.table(
        "feature_permissions",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("role", sa.String()),
        sa.column("feature", sa.String()),
    )
    op.bulk_insert(feature_permissions, [
        {"id": uuid.uuid4(), "role": role, "feature": feature}
        for role in ("cataloger", "editor")
        for feature in _NEW_FEATURES
    ])


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM feature_permissions WHERE feature IN ('media', 'batch')"))
    op.drop_constraint("ck_feature_permission_feature", "feature_permissions", type_="check")
    op.create_check_constraint(
        "ck_feature_permission_feature",
        "feature_permissions",
        sa.text(
            "feature IN ('export', 'sparql', 'import', 'working_sets', 'audit_log', "
            "'vocab_terms', 'vocab_structure', 'schema', 'subtypes', 'form_variants', "
            "'storage_locations', 'pages', 'oai_sets', 'banners', "
            "'manual_lock', 'force_unlock', 'users', 'settings', 'api_keys')"
        ),
    )
