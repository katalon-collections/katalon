import uuid
from datetime import UTC, date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from katalon.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Primary types
# ---------------------------------------------------------------------------


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    idno: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    collection_status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict[str, Any])
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}

    media_files: Mapped[list["MediaFile"]] = relationship(
        back_populates="object", cascade="all, delete-orphan", passive_deletes=True
    )
    media_import_references: Mapped[list["MediaImportReference"]] = relationship(
        back_populates="object", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_objects_metadata_gin", "metadata", postgresql_using="gin"),
        Index("ix_objects_search_vector", "search_vector", postgresql_using="gin"),
    )


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    idno: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict[str, Any])
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (
        Index("ix_entities_metadata_gin", "metadata", postgresql_using="gin"),
    )


class Place(Base):
    __tablename__ = "places"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    idno: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    place_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    geom: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict[str, Any])
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (
        Index("ix_places_metadata_gin", "metadata", postgresql_using="gin"),
        Index("ix_places_geom", "geom", postgresql_using="gist"),
    )


class Occurrence(Base):
    __tablename__ = "occurrences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    idno: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    occurrence_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict[str, Any])
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (
        Index("ix_occurrences_metadata_gin", "metadata", postgresql_using="gin"),
    )


class Procedure(Base):
    __tablename__ = "procedures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    idno: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    procedure_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    reference_number: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict[str, Any])
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (
        Index("ix_procedures_metadata_gin", "metadata", postgresql_using="gin"),
    )


# ---------------------------------------------------------------------------
# Schema / field definitions
# ---------------------------------------------------------------------------


class FieldDefinition(Base):
    __tablename__ = "field_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # object/entity/place/occurrence/procedure
    target_type: Mapped[str] = mapped_column(String(32), index=True)
    # e.g. person, organisation
    target_subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    label: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])  # {"de": "...", "en": "..."}
    # text/date/number/geo/vocab/relation/boolean/group
    field_type: Mapped[str] = mapped_column(String(32))
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_translatable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_searchable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])
    show_in_detail: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    show_in_list: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Controls anonymous output. Internal fields stay available to authenticated staff.
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_facet: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # NULL for top-level fields; set for sub-fields of a group field
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("field_definitions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    children: Mapped[list["FieldDefinition"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="FieldDefinition.sort_order",
    )
    parent: Mapped["FieldDefinition | None"] = relationship(
        back_populates="children",
        remote_side="FieldDefinition.id",
    )
    metadata_mappings: Mapped[list["MetadataMapping"]] = relationship(
        back_populates="field_definition",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_field_defs_target_type", "target_type"),
    )


class MetadataMapping(Base):
    __tablename__ = "metadata_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    field_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("field_definitions.id", ondelete="CASCADE"),
        index=True,
    )
    format_key: Mapped[str] = mapped_column(String(64), index=True)
    target_path: Mapped[str] = mapped_column(String(256))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    field_definition: Mapped[FieldDefinition] = relationship(back_populates="metadata_mappings")

    __table_args__ = (
        UniqueConstraint(
            "field_definition_id",
            "format_key",
            "target_path",
            name="uq_metadata_mappings_field_format_target",
        ),
        Index("ix_metadata_mappings_format_enabled", "format_key", "is_enabled"),
    )


class ImportMapping(Base):
    __tablename__ = "import_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    record_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_selector: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mapping: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_import_mappings_record_type", "record_type"),
    )


class RecordSubtype(Base):
    __tablename__ = "record_subtypes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # object/entity/place/occurrence
    primary_type: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(64))
    label: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])  # {"de": "...", "en": "..."}
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("primary_type", "name", name="uq_record_subtypes_primary_name"),
    )


class FormVariant(Base):
    __tablename__ = "form_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # object/entity/place/occurrence/procedure
    target_type: Mapped[str] = mapped_column(String(32), index=True)
    target_subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    label: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])  # {"de": "...", "en": "..."}
    # ordered list of FieldDefinition.name for this target_type/subtype
    field_names: Mapped[list[Any]] = mapped_column(JSONB, default=list[Any])
    is_default_global: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    role_defaults: Mapped[list["FormVariantRoleDefault"]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_form_variants_target_type", "target_type"),
    )


class FormVariantRoleDefault(Base):
    __tablename__ = "form_variant_role_defaults"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    target_type: Mapped[str] = mapped_column(String(32), index=True)
    target_subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(32))
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_variants.id", ondelete="CASCADE"),
        index=True,
    )

    variant: Mapped[FormVariant] = relationship(back_populates="role_defaults")

    __table_args__ = (
        UniqueConstraint(
            "target_type", "target_subtype", "role",
            name="uq_form_variant_role_defaults_scope_role",
        ),
    )


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------


class Vocabulary(Base):
    __tablename__ = "vocabularies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    is_hierarchical: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[str] = mapped_column(String(16), default="term", server_default="term")

    terms: Mapped[list["VocabularyTerm"]] = relationship(
        back_populates="vocabulary", cascade="all, delete-orphan", passive_deletes=True
    )


class VocabularyTerm(Base):
    __tablename__ = "vocabulary_terms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    vocabulary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vocabularies.id", ondelete="CASCADE"), index=True
    )
    term: Mapped[str] = mapped_column(String(256))
    label: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])  # {"de": "...", "en": "..."}
    inverse_label: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])  # {"de": "...", "en": "..."}
    # For relation vocabularies: record types this term may connect.
    # Empty list = unrestricted. Only meaningful when vocabulary.kind == "relation".
    applies_from: Mapped[list[Any]] = mapped_column(JSONB, default=list[Any])
    applies_to: Mapped[list[Any]] = mapped_column(JSONB, default=list[Any])
    # Values for vocabulary_term field definitions.
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict[str, Any])
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vocabulary_terms.id", ondelete="SET NULL"), nullable=True
    )

    vocabulary: Mapped["Vocabulary"] = relationship(back_populates="terms")
    children: Mapped[list["VocabularyTerm"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped["VocabularyTerm | None"] = relationship(
        back_populates="children", remote_side="VocabularyTerm.id"
    )


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------


class Relation(Base):
    __tablename__ = "relations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    from_type: Mapped[str] = mapped_column(String(32))
    from_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    to_type: Mapped[str] = mapped_column(String(32))
    to_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    relation_type: Mapped[str] = mapped_column(String(128))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict[str, Any])
    is_schema_derived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (
        Index("ix_relations_from", "from_type", "from_id"),
        Index("ix_relations_to", "to_type", "to_id"),
    )


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("objects.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    file_path: Mapped[str] = mapped_column(String(1024))
    iiif_manifest: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    media_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    license_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rights_holder: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    object: Mapped["Object"] = relationship(back_populates="media_files")


class MediaImportReference(Base):
    __tablename__ = "media_import_references"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("objects.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    normalized_filename: Mapped[str] = mapped_column(String(512), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    object: Mapped["Object"] = relationship(back_populates="media_import_references")

    __table_args__ = (
        UniqueConstraint(
            "object_id",
            "normalized_filename",
            name="uq_media_import_references_object_filename",
        ),
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    record_type: Mapped[str] = mapped_column(String(32), index=True)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32))  # create/update/delete/publish
    changed_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    __table_args__ = (
        Index("ix_audit_log_record", "record_type", "record_id"),
    )


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


class RecordSnapshot(Base):
    __tablename__ = "record_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    record_type: Mapped[str] = mapped_column(String(32), index=True)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    label: Mapped[str] = mapped_column(String(256))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ---------------------------------------------------------------------------
# Authority sources
# ---------------------------------------------------------------------------


class AuthoritySource(Base):
    __tablename__ = "authority_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(256))
    adapter_class: Mapped[str] = mapped_column(String(256))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# Static pages (FAQ, Impressum, etc.)
# ---------------------------------------------------------------------------


class StaticPage(Base):
    __tablename__ = "static_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])    # {"de": "...", "en": "..."}
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])  # {"de": "Markdown...", "en": "..."}
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


# ---------------------------------------------------------------------------
# Portal configuration (singleton row, key="default")
# ---------------------------------------------------------------------------


class PortalConfig(Base):
    __tablename__ = "portal_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    site_title: Mapped[str] = mapped_column(String(256), default="Katalon")
    site_subtitle: Mapped[str] = mapped_column(String(512), default="")
    hero_text: Mapped[str] = mapped_column(Text, default="")
    featured_object_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list[Any])
    # e.g. {"object": ["creator"], "entity": []}
    facet_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])
    browse_enabled_types: Mapped[list[str]] = mapped_column(
        JSONB, default=lambda: ["object", "entity", "place", "occurrence"]
    )
    accent_color: Mapped[str] = mapped_column(String(32), default="#1e3a8a")
    logo_url: Mapped[str] = mapped_column(String(512), default="")
    placeholder_image_url: Mapped[str] = mapped_column(String(512), default="")
    color_tokens: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])  # extra CSS var overrides
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


# ---------------------------------------------------------------------------
# OAI-PMH Sets (query-based, admin-configurable)
# ---------------------------------------------------------------------------


class OAISet(Base):
    __tablename__ = "oai_sets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    set_spec: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    set_name: Mapped[str] = mapped_column(String(256))
    filter_record_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    filter_q: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    filter_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), default="viewer")  # superuser/admin/editor/viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    role: Mapped[str] = mapped_column(String(32), index=True)
    record_type: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(16))

    __table_args__ = (
        UniqueConstraint("role", "record_type", "action", name="uq_role_permission"),
    )


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    # first chars for display/lookup
    key_prefix: Mapped[str] = mapped_column(String(16), index=True)
    hashed_key: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="api_keys")


# ---------------------------------------------------------------------------
# Admin configuration (singleton row, key="default")
# ---------------------------------------------------------------------------


class AdminConfig(Base):
    __tablename__ = "admin_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True, default="default")
    # {"object": "ulb_x_{counter:05d}", ...}
    idno_schemas: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])
    # {"object": "^ulb_x_\\d{5}$", ...}
    idno_patterns: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict[str, Any])
    reconciliation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reconciliation_threshold: Mapped[int] = mapped_column(Integer, default=5)
    reconciliation_id_diff_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Ordered content languages; first entry is the primary/fallback language.
    supported_languages: Mapped[list[Any]] = mapped_column(JSONB, default=list[Any])
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ai_max_input_tokens: Mapped[int] = mapped_column(Integer, default=6000)
    ai_max_output_tokens: Mapped[int] = mapped_column(Integer, default=800)
    ai_daily_user_token_limit: Mapped[int] = mapped_column(Integer, default=50000)
    ai_monthly_global_token_limit: Mapped[int] = mapped_column(Integer, default=1000000)
    media_default_license_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    media_default_rights_holder: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class AppSecret(Base):
    __tablename__ = "app_secrets"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    encrypted_value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class AIUsageEvent(Base):
    __tablename__ = "ai_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(256), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    __table_args__ = (
        Index("ix_ai_usage_events_user_created", "user_id", "created_at"),
        Index("ix_ai_usage_events_created", "created_at"),
    )


# ---------------------------------------------------------------------------
# IDNO counters (one row per primary type, incremented atomically)
# ---------------------------------------------------------------------------


class IdnoCounter(Base):
    __tablename__ = "idno_counters"

    record_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# Maintenance / Info Banners
# ---------------------------------------------------------------------------


class Banner(Base):
    __tablename__ = "banners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    message: Mapped[str] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(32), default="blue")  # blue/yellow/red/green
    # which surfaces show this banner
    show_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    show_portal: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
