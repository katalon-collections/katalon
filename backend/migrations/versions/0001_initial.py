"""Initial schema: all 4 primary types + supporting tables

Revision ID: 0001
Revises:
Create Date: 2026-04-30

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column("hashed_password", sa.Text, nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Objects
    op.create_table(
        "objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idno", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_objects_idno", "objects", ["idno"], unique=True)
    op.create_index("ix_objects_status", "objects", ["status"])
    op.create_index("ix_objects_metadata_gin", "objects", ["metadata"], postgresql_using="gin")
    op.create_index("ix_objects_search_vector", "objects", ["search_vector"], postgresql_using="gin")

    # Entities
    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"])
    op.create_index("ix_entities_status", "entities", ["status"])
    op.create_index("ix_entities_metadata_gin", "entities", ["metadata"], postgresql_using="gin")

    # Places
    op.create_table(
        "places",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "ALTER TABLE places ADD COLUMN geom geometry(Point, 4326)"
    )
    op.execute("CREATE INDEX ix_places_geom ON places USING gist(geom)")
    op.create_index("ix_places_status", "places", ["status"])
    op.create_index("ix_places_metadata_gin", "places", ["metadata"], postgresql_using="gin")

    # Occurrences
    op.create_table(
        "occurrences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurrence_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_occurrences_occurrence_type", "occurrences", ["occurrence_type"])
    op.create_index("ix_occurrences_status", "occurrences", ["status"])
    op.create_index("ix_occurrences_metadata_gin", "occurrences", ["metadata"], postgresql_using="gin")

    # Field definitions
    op.create_table(
        "field_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("label", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("field_type", sa.String(32), nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_repeatable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("target_type", "name", name="uq_field_def_type_name"),
    )
    op.create_index("ix_field_defs_target_type", "field_definitions", ["target_type"])

    # Vocabularies
    op.create_table(
        "vocabularies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_hierarchical", sa.Boolean, nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vocabularies_name", "vocabularies", ["name"], unique=True)

    op.create_table(
        "vocabulary_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vocabulary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("term", sa.String(256), nullable=False),
        sa.Column("label", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["vocabulary_id"], ["vocabularies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["vocabulary_terms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vocab_terms_vocabulary_id", "vocabulary_terms", ["vocabulary_id"])

    # Relations
    op.create_table(
        "relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_type", sa.String(32), nullable=False),
        sa.Column("from_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_type", sa.String(32), nullable=False),
        sa.Column("to_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation_type", sa.String(128), nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_relations_from", "relations", ["from_type", "from_id"])
    op.create_index("ix_relations_to", "relations", ["to_type", "to_id"])

    # Media files
    op.create_table(
        "media_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("iiif_manifest", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_files_object_id", "media_files", ["object_id"])

    # Audit log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(32), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("changed_fields", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_record", "audit_log", ["record_type", "record_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # Snapshots
    op.create_table(
        "record_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(32), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("snapshot", postgresql.JSONB, nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # Authority sources
    op.create_table(
        "authority_sources",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("label", sa.String(256), nullable=False),
        sa.Column("adapter_class", sa.String(256), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for table in [
        "authority_sources", "record_snapshots", "audit_log",
        "media_files", "relations", "vocabulary_terms", "vocabularies",
        "field_definitions", "occurrences", "places", "entities", "objects", "users",
    ]:
        op.drop_table(table)
