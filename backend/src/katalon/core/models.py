import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from katalon.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Primary types
# ---------------------------------------------------------------------------


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    idno: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    media_files: Mapped[list["MediaFile"]] = relationship(back_populates="object")

    __table_args__ = (
        Index("ix_objects_metadata_gin", "metadata", postgresql_using="gin"),
        Index("ix_objects_search_vector", "search_vector", postgresql_using="gin"),
    )


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_entities_metadata_gin", "metadata", postgresql_using="gin"),
    )


class Place(Base):
    __tablename__ = "places"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    geom: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_places_metadata_gin", "metadata", postgresql_using="gin"),
        Index("ix_places_geom", "geom", postgresql_using="gist"),
    )


class Occurrence(Base):
    __tablename__ = "occurrences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    occurrence_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_occurrences_metadata_gin", "metadata", postgresql_using="gin"),
    )


# ---------------------------------------------------------------------------
# Schema / field definitions
# ---------------------------------------------------------------------------


class FieldDefinition(Base):
    __tablename__ = "field_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    target_type: Mapped[str] = mapped_column(String(32), index=True)  # object/entity/place/occurrence
    target_subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)  # e.g. person, organisation
    name: Mapped[str] = mapped_column(String(128))
    label: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"de": "...", "en": "..."}
    field_type: Mapped[str] = mapped_column(String(32))  # text/date/number/geo/vocab/relation/boolean
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    __table_args__ = (
        Index("ix_field_defs_target_type", "target_type"),
    )


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------


class Vocabulary(Base):
    __tablename__ = "vocabularies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    is_hierarchical: Mapped[bool] = mapped_column(Boolean, default=False)

    terms: Mapped[list["VocabularyTerm"]] = relationship(back_populates="vocabulary")


class VocabularyTerm(Base):
    __tablename__ = "vocabulary_terms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    vocabulary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vocabularies.id", ondelete="CASCADE"), index=True
    )
    term: Mapped[str] = mapped_column(String(256))
    label: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"de": "...", "en": "..."}
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
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
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
    iiif_manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    media_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    object: Mapped["Object"] = relationship(back_populates="media_files")


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
    changed_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
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
    snapshot: Mapped[dict] = mapped_column(JSONB)
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
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), default="viewer")  # admin/editor/viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
