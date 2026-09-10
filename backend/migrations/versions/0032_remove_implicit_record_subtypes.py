"""remove implicit record subtypes

Revision ID: 0032
Revises: 0031
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("entities", "entity_type", existing_type=sa.String(length=64), nullable=True)
    op.alter_column("occurrences", "occurrence_type", existing_type=sa.String(length=64), nullable=True)

    implicit_subtypes = {
        "object": "objekt",
        "entity": "person",
        "place": "geographikum",
        "occurrence": "werk",
    }
    updates = (
        (sa.text("UPDATE objects SET object_type = NULL WHERE object_type = :subtype"), "object"),
        (sa.text("UPDATE entities SET entity_type = NULL WHERE entity_type = :subtype"), "entity"),
        (sa.text("UPDATE places SET place_type = NULL WHERE place_type = :subtype"), "place"),
        (sa.text("UPDATE occurrences SET occurrence_type = NULL WHERE occurrence_type = :subtype"), "occurrence"),
    )
    for statement, primary_type in updates:
        subtype = implicit_subtypes[primary_type]
        op.execute(statement.bindparams(subtype=subtype))
        op.execute(
            sa.text(
                "DELETE FROM record_subtypes WHERE primary_type = :primary_type AND name = :subtype"
            ).bindparams(primary_type=primary_type, subtype=subtype)
        )
        op.execute(
            sa.text(
                "UPDATE field_definitions SET target_subtype = NULL "
                "WHERE target_type = :primary_type AND target_subtype = :subtype"
            ).bindparams(primary_type=primary_type, subtype=subtype)
        )
        op.execute(
            sa.text(
                "UPDATE form_variants SET target_subtype = NULL "
                "WHERE target_type = :primary_type AND target_subtype = :subtype"
            ).bindparams(primary_type=primary_type, subtype=subtype)
        )
        op.execute(
            sa.text(
                "UPDATE form_variant_role_defaults SET target_subtype = NULL "
                "WHERE target_type = :primary_type AND target_subtype = :subtype"
            ).bindparams(primary_type=primary_type, subtype=subtype)
        )

    for primary_type, subtype in implicit_subtypes.items():
        op.execute(
            sa.text(
                "UPDATE field_definitions SET settings = settings - 'target_subtype' "
                "WHERE settings->>'target_type' = :primary_type "
                "AND settings->>'target_subtype' = :subtype"
            ).bindparams(primary_type=primary_type, subtype=subtype)
        )

def downgrade() -> None:
    for primary_type, subtype, label_de, label_en in (
        ("object", "objekt", "Objekt", "Object"),
        ("entity", "person", "Person", "Person"),
        ("place", "geographikum", "Geographikum", "Geographic"),
        ("occurrence", "werk", "Werk", "Work"),
    ):
        op.execute(
            sa.text(
                "INSERT INTO record_subtypes (id, primary_type, name, label, sort_order, is_default) "
                "SELECT :id, :primary_type, :subtype, "
                "jsonb_build_object('de', :label_de, 'en', :label_en), 0, false "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM record_subtypes WHERE primary_type = :primary_type AND name = :subtype"
                ")"
            ).bindparams(
                id=uuid.uuid4(),
                primary_type=primary_type,
                subtype=subtype,
                label_de=label_de,
                label_en=label_en,
            )
        )
    op.execute(sa.text("UPDATE entities SET entity_type = 'person' WHERE entity_type IS NULL"))
    op.execute(sa.text("UPDATE occurrences SET occurrence_type = 'werk' WHERE occurrence_type IS NULL"))
    op.alter_column("occurrences", "occurrence_type", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("entities", "entity_type", existing_type=sa.String(length=64), nullable=False)
