# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""export_mapping_sets: Versionierte Export-Mapping-Sets und flexible Regeln

Revision ID: 0058
Revises: 0057
Create Date: 2026-09-08
"""
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create export_mapping_sets
    op.create_table(
        "export_mapping_sets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("format_key", sa.String(64), nullable=False),
        sa.Column("profile_id", sa.String(128), nullable=False),
        sa.Column("profile_version", sa.String(32), nullable=False, server_default="1.0"),
        sa.Column("record_type", sa.String(64), nullable=False),
        sa.Column("target_subtype", sa.String(128), nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "based_on_id",
            UUID(as_uuid=True),
            sa.ForeignKey("export_mapping_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("institution_config", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_export_mapping_sets_format_key", "export_mapping_sets", ["format_key"])
    op.create_index("ix_export_mapping_sets_record_type", "export_mapping_sets", ["record_type"])
    op.create_index("ix_export_mapping_sets_status", "export_mapping_sets", ["status"])
    op.create_index(
        "ix_export_mapping_sets_lookup",
        "export_mapping_sets",
        ["format_key", "record_type", "status"],
    )

    # Unique constraint: exactly one published set per (format_key, profile_id, record_type, target_subtype)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_export_mapping_sets_published
        ON export_mapping_sets (format_key, profile_id, record_type, coalesce(target_subtype, ''))
        WHERE status = 'published'
        """
    )

    # 2. Create export_mapping_rules
    op.create_table(
        "export_mapping_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_key", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "mapping_set_id",
            UUID(as_uuid=True),
            sa.ForeignKey("export_mapping_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(32), nullable=False, server_default="field"),
        sa.Column(
            "field_definition_id",
            UUID(as_uuid=True),
            sa.ForeignKey("field_definitions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_config", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("target_key", sa.String(256), nullable=False),
        sa.Column("settings", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_export_mapping_rules_rule_key", "export_mapping_rules", ["rule_key"])
    op.create_index("ix_export_mapping_rules_set_id", "export_mapping_rules", ["mapping_set_id"])
    op.create_index("ix_export_mapping_rules_set_order", "export_mapping_rules", ["mapping_set_id", "sort_order"])
    op.create_index("ix_export_mapping_rules_field_def", "export_mapping_rules", ["field_definition_id"])

    # 3. Data migration: migrate existing metadata_mappings into published export_mapping_sets
    conn = op.get_bind()
    mappings_data = conn.execute(
        sa.text(
            """
            SELECT mm.id, mm.field_definition_id, mm.format_key, mm.target_path,
                   mm.settings, mm.sort_order, mm.is_enabled, mm.created_at, mm.updated_at,
                   fd.target_type, fd.name as field_name, fd.field_type
            FROM metadata_mappings mm
            JOIN field_definitions fd ON mm.field_definition_id = fd.id
            ORDER BY fd.target_type, mm.format_key, mm.sort_order
            """
        )
    ).fetchall()

    if mappings_data:
        # Group by (format_key, target_type)
        grouped: dict[tuple[str, str], list[dict]] = {}
        for row in mappings_data:
            key = (row.format_key, row.target_type)
            grouped.setdefault(key, []).append(row)

        profile_id_map = {
            "oai_dc": "oai_dc_simple",
            "lido": "lido_core",
            "mets_mods": "mets_mods_core",
            "json_ld": "jsonld_cidoc_lrmoo",
        }

        now_val = datetime.now(UTC)
        for (format_key, target_type), rows in grouped.items():
            set_id = uuid.uuid4()
            profile_id = profile_id_map.get(format_key, f"{format_key}_default")
            name = f"{format_key.upper()} Mapping ({target_type})"

            conn.execute(
                sa.text(
                    """
                    INSERT INTO export_mapping_sets (
                        id, format_key, profile_id, profile_version, record_type, target_subtype,
                        name, status, revision, institution_config, version, created_at, updated_at, published_at
                    ) VALUES (
                        :id, :format_key, :profile_id, '1.0', :record_type, NULL,
                        :name, 'published', 1, '{}'::jsonb, 1, :now, :now, :now
                    )
                    """
                ),
                {
                    "id": set_id,
                    "format_key": format_key,
                    "profile_id": profile_id,
                    "record_type": target_type,
                    "name": name,
                    "now": now_val,
                },
            )

            for r in rows:
                rule_id = uuid.uuid4()
                source_config_json = json.dumps({"field_name": r.field_name, "field_type": r.field_type})
                settings_json = json.dumps(dict(r.settings or {}))
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO export_mapping_rules (
                            id, rule_key, mapping_set_id, source_kind, field_definition_id,
                            source_config, target_key, settings, sort_order, is_enabled,
                            created_at, updated_at
                        ) VALUES (
                            :id, :rule_key, :mapping_set_id, 'field', :field_definition_id,
                            :source_config::jsonb, :target_key, :settings::jsonb, :sort_order, :is_enabled,
                            :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "id": rule_id,
                        "rule_key": r.id,
                        "mapping_set_id": set_id,
                        "field_definition_id": r.field_definition_id,
                        "source_config": source_config_json,
                        "target_key": r.target_path,
                        "settings": settings_json,
                        "sort_order": r.sort_order,
                        "is_enabled": r.is_enabled,
                        "created_at": r.created_at,
                        "updated_at": r.updated_at,
                    },
                )

    # 4. Drop old metadata_mappings table
    op.drop_table("metadata_mappings")


def downgrade() -> None:
    # 1. Recreate metadata_mappings table
    op.create_table(
        "metadata_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "field_definition_id",
            UUID(as_uuid=True),
            sa.ForeignKey("field_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format_key", sa.String(64), nullable=False),
        sa.Column("target_path", sa.String(256), nullable=False),
        sa.Column("settings", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "field_definition_id",
            "format_key",
            "target_path",
            name="uq_metadata_mappings_field_format_target",
        ),
    )
    op.create_index("ix_metadata_mappings_field_definition_id", "metadata_mappings", ["field_definition_id"])
    op.create_index("ix_metadata_mappings_format_key", "metadata_mappings", ["format_key"])
    op.create_index("ix_metadata_mappings_format_enabled", "metadata_mappings", ["format_key", "is_enabled"])

    conn = op.get_bind()

    # Check for non-field rules: cannot downgrade complex rules without loss
    non_field_rules = conn.execute(
        sa.text("SELECT COUNT(*) FROM export_mapping_rules WHERE source_kind != 'field'")
    ).scalar()

    if non_field_rules and non_field_rules > 0:
        raise RuntimeError(
            f"Downgrade abgebrochen: {non_field_rules} komplexe ExportMappingRule(s) mit source_kind != 'field' vorhanden. "
            "Ein Downgrade auf die flache Tabelle 'metadata_mappings' würde diese Regeln stillschweigend verlieren."
        )

    # Restore published field rules into metadata_mappings
    conn.execute(
        sa.text(
            """
            INSERT INTO metadata_mappings (
                id, field_definition_id, format_key, target_path,
                settings, sort_order, is_enabled, created_at, updated_at
            )
            SELECT r.rule_key, r.field_definition_id, s.format_key, r.target_key,
                   r.settings, r.sort_order, r.is_enabled, r.created_at, r.updated_at
            FROM export_mapping_rules r
            JOIN export_mapping_sets s ON r.mapping_set_id = s.id
            WHERE s.status = 'published' AND r.field_definition_id IS NOT NULL
            ON CONFLICT (field_definition_id, format_key, target_path) DO NOTHING
            """
        )
    )

    op.drop_table("export_mapping_rules")
    op.execute("DROP INDEX IF EXISTS uq_export_mapping_sets_published")
    op.drop_table("export_mapping_sets")
