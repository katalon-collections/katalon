"""make procedure types configurable record subtypes

Revision ID: 0034
Revises: 0033
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SYSTEM_PROCEDURE_TYPES = (
    ("loan_out", "Ausleihe ausgehend", "Outgoing loan"),
    ("loan_in", "Ausleihe eingehend", "Incoming loan"),
    ("acquisition", "Erwerbung", "Acquisition"),
    ("conservation", "Restaurierung", "Conservation"),
    ("object_entry", "Objekteingang", "Object entry"),
    ("deaccession", "Deakzession", "Deaccession"),
)


def upgrade() -> None:
    for sort_order, (name, label_de, label_en) in enumerate(SYSTEM_PROCEDURE_TYPES):
        op.execute(
            sa.text(
                "INSERT INTO record_subtypes (id, primary_type, name, label, sort_order, is_default) "
                "SELECT :id, 'procedure', :name, jsonb_build_object('de', :label_de, 'en', :label_en), "
                ":sort_order, false WHERE NOT EXISTS ("
                "SELECT 1 FROM record_subtypes WHERE primary_type = 'procedure' AND name = :name)"
            ).bindparams(
                id=uuid.uuid4(),
                name=name,
                label_de=label_de,
                label_en=label_en,
                sort_order=sort_order,
            )
        )


def downgrade() -> None:
    for name, _, _ in SYSTEM_PROCEDURE_TYPES:
        op.execute(
            sa.text(
                "DELETE FROM record_subtypes WHERE primary_type = 'procedure' AND name = :name"
            ).bindparams(name=name)
        )
