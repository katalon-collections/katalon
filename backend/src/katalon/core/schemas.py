import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class StatusEnum(str):
    draft = "draft"
    internal = "internal"
    public = "public"


# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

class FieldDefinitionCreate(BaseModel):
    target_type: str
    name: str
    label: dict = {}
    field_type: str
    is_required: bool = False
    is_repeatable: bool = False
    sort_order: int = 0
    settings: dict = {}


class FieldDefinitionRead(FieldDefinitionCreate):
    id: uuid.UUID

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------

class VocabularyCreate(BaseModel):
    name: str
    is_hierarchical: bool = False


class VocabularyRead(VocabularyCreate):
    id: uuid.UUID

    class Config:
        from_attributes = True


class VocabularyTermCreate(BaseModel):
    vocabulary_id: uuid.UUID
    term: str
    label: dict = {}
    parent_id: uuid.UUID | None = None


class VocabularyTermRead(VocabularyTermCreate):
    id: uuid.UUID

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Primary record types (shared base)
# ---------------------------------------------------------------------------

class RecordBase(BaseModel):
    status: str = "draft"
    metadata_: dict = {}

    class Config:
        from_attributes = True
        populate_by_name = True


class ObjectCreate(RecordBase):
    idno: str | None = None


class ObjectRead(ObjectCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class EntityCreate(RecordBase):
    entity_type: str


class EntityRead(EntityCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PlaceCreate(RecordBase):
    lat: float | None = None
    lon: float | None = None


class PlaceRead(PlaceCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class OccurrenceCreate(RecordBase):
    occurrence_type: str


class OccurrenceRead(OccurrenceCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------

class RelationCreate(BaseModel):
    from_type: str
    from_id: uuid.UUID
    to_type: str
    to_id: uuid.UUID
    relation_type: str
    metadata_: dict = {}


class RelationRead(RelationCreate):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "viewer"


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: uuid.UUID
    role: str


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class Page(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class AuditLogRead(BaseModel):
    id: uuid.UUID
    record_type: str
    record_id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    changed_fields: dict
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

class SnapshotCreate(BaseModel):
    label: str


class SnapshotRead(SnapshotCreate):
    id: uuid.UUID
    record_type: str
    record_id: uuid.UUID
    snapshot: dict
    created_by: uuid.UUID | None
    created_at: datetime

    class Config:
        from_attributes = True
