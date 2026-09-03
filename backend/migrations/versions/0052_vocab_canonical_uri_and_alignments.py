# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""add canonical_uri to vocabularies and uri/exact_match_uris to vocabulary_terms

Revision ID: 0052
Revises: 0051
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vocabularies",
        sa.Column("canonical_uri", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "vocabulary_terms",
        sa.Column("uri", sa.String(length=512), nullable=True),
    )
    op.create_index(
        op.f("ix_vocabulary_terms_uri"),
        "vocabulary_terms",
        ["uri"],
        unique=False,
    )
    op.add_column(
        "vocabulary_terms",
        sa.Column(
            "exact_match_uris",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("vocabulary_terms", "exact_match_uris")
    op.drop_index(op.f("ix_vocabulary_terms_uri"), table_name="vocabulary_terms")
    op.drop_column("vocabulary_terms", "uri")
    op.drop_column("vocabularies", "canonical_uri")
