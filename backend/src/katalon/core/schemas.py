import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


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
    target_subtype: str | None = None
    name: str
    label: dict = {}
    field_type: str
    is_required: bool = False
    is_repeatable: bool = False
    sort_order: int = 0
    settings: dict = {}
    show_in_detail: bool = True


class FieldDefinitionRead(FieldDefinitionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_deleted: bool = False


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------

class VocabularyCreate(BaseModel):
    name: str
    is_hierarchical: bool = False


class VocabularyRead(VocabularyCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class VocabularyTermCreate(BaseModel):
    vocabulary_id: uuid.UUID
    term: str
    label: dict = {}
    parent_id: uuid.UUID | None = None


class VocabularyTermRead(VocabularyTermCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


# ---------------------------------------------------------------------------
# Primary record types (shared base)
# ---------------------------------------------------------------------------

class RecordBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    status: str = "draft"
    metadata_: dict = {}


class ObjectCreate(RecordBase):
    idno: str | None = None


class ObjectRead(ObjectCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class EntityCreate(RecordBase):
    idno: str | None = None
    entity_type: str


class EntityRead(EntityCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PlaceCreate(RecordBase):
    idno: str | None = None
    lat: float | None = None
    lon: float | None = None


class PlaceRead(PlaceCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class OccurrenceCreate(RecordBase):
    idno: str | None = None
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
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "viewer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

class ApiKeyCreate(BaseModel):
    name: str
    expires_at: datetime | None = None


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None


class ApiKeyCreated(ApiKeyRead):
    """Returned only once at creation – contains the full plaintext key."""
    key: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: uuid.UUID
    role: str


# ---------------------------------------------------------------------------
# OAI Sets
# ---------------------------------------------------------------------------

class OAISetCreate(BaseModel):
    set_spec: str
    set_name: str
    filter_record_type: str | None = None
    filter_q: str | None = None
    filter_status: str | None = None
    filter_metadata: dict = {}


class OAISetRead(OAISetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


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
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    record_type: str
    record_id: uuid.UUID
    record_label: str | None = None
    user_id: uuid.UUID | None
    user_name: str | None = None
    action: str
    changed_fields: dict
    created_at: datetime


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

class SnapshotCreate(BaseModel):
    label: str


class SnapshotRead(SnapshotCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    record_type: str
    record_id: uuid.UUID
    snapshot: dict
    created_by: uuid.UUID | None
    created_at: datetime
