"""Add immutable vocabulary kind.

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vocabularies", sa.Column("kind", sa.String(16), nullable=True))
    op.execute(
        """
        UPDATE vocabularies
        SET kind = 'relation'
        WHERE name = 'relation_types'
           OR id::text IN (
            SELECT settings->>'relation_type_vocab'
            FROM field_definitions
            WHERE settings ? 'relation_type_vocab'
        )
        """
    )
    op.execute("UPDATE vocabularies SET kind = 'term' WHERE kind IS NULL")
    op.alter_column(
        "vocabularies",
        "kind",
        existing_type=sa.String(16),
        nullable=False,
        server_default="term",
    )


def downgrade() -> None:
    op.drop_column("vocabularies", "kind")
