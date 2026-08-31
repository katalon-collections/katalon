import uuid
from datetime import date, datetime
from typing import Annotated, Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

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
    label: dict[str, Any] = {}
    field_type: str
    is_required: bool = False
    is_repeatable: bool = False
    is_translatable: bool = False
    is_searchable: bool = True
    sort_order: int = 0
    settings: dict[str, Any] = {}
    show_in_detail: bool = True
    show_in_list: bool = True
    detail_slot: Literal["main", "sidebar"] = "sidebar"
    detail_role: Literal["none", "description"] = "none"
    is_public: bool = True
    is_facet: bool = False
    parent_id: uuid.UUID | None = None


class FieldDefinitionRead(FieldDefinitionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_deleted: bool = False
    children: list["FieldDefinitionRead"] = []


FieldDefinitionRead.model_rebuild()


class MetadataMappingCreate(BaseModel):
    field_definition_id: uuid.UUID
    format_key: str
    target_path: str
    settings: dict[str, Any] = {}
    sort_order: int = 0
    is_enabled: bool = True


class MetadataMappingRead(MetadataMappingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MetadataMappingUpsert(BaseModel):
    target_path: str | None = None
    settings: dict[str, Any] = {}
    sort_order: int = 0
    is_enabled: bool = True


class ImportMappingCreate(BaseModel):
    name: str
    record_type: str
    subtype: str | None = None
    media_selector: str | None = None
    mapping: dict[str, Any]


class ImportMappingUpdate(BaseModel):
    name: str | None = None
    subtype: str | None = None
    media_selector: str | None = None
    mapping: dict[str, Any] | None = None


class ImportMappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    record_type: str
    subtype: str | None = None
    media_selector: str | None = None
    mapping: dict[str, Any]
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class RecordSubtypeCreate(BaseModel):
    primary_type: str
    name: str
    label: dict[str, Any] = {}
    description: str = ""
    sort_order: int = 0
    is_default: bool = False


class RecordSubtypeRead(RecordSubtypeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class FormVariantCreate(BaseModel):
    target_type: str
    target_subtype: str | None = None
    name: str
    label: dict[str, Any] = {}
    field_names: list[str] = []
    is_default_global: bool = False
    sort_order: int = 0


class FormVariantRoleDefaultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str


class FormVariantRead(FormVariantCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_deleted: bool = False
    # roles for which this variant is the default, scoped to target_type/target_subtype;
    # populated only from the requesting user's own role by the list endpoint
    default_for_roles: list[str] = []


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------

class VocabularyCreate(BaseModel):
    name: str
    is_hierarchical: bool = False
    kind: Literal["term", "relation"] = "term"


class VocabularyRead(VocabularyCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    @computed_field(alias="_links")
    def links(self) -> dict[str, dict[str, str]]:
        base = f"/v1/vocabularies/{self.id}"
        return {
            "self": {"href": base},
            "terms": {"href": f"{base}/terms"},
            "tree": {"href": f"{base}/tree"},
        }


RECORD_TYPES = ("object", "entity", "place", "occurrence", "procedure")


class VocabularyTermCreate(BaseModel):
    vocabulary_id: uuid.UUID
    term: str
    label: dict[str, Any] = {}
    inverse_label: dict[str, Any] = {}
    metadata_: dict[str, Any] = {}
    parent_id: uuid.UUID | None = None
    applies_from: list[str] = []
    applies_to: list[str] = []

    @field_validator("applies_from", "applies_to")
    @classmethod
    def _validate_applies(cls, v: list[str]) -> list[str]:
        invalid = [t for t in v if t not in RECORD_TYPES]
        if invalid:
            raise ValueError(f"Ungültige Record-Typen: {invalid}")
        return v


class VocabularyTermRead(VocabularyTermCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID

    @computed_field(alias="_links")
    def links(self) -> dict[str, dict[str, str]]:
        base = f"/v1/vocabularies/{self.vocabulary_id}/terms/{self.id}"
        links = {
            "self": {"href": base},
            "vocabulary": {"href": f"/v1/vocabularies/{self.vocabulary_id}"},
            "ancestors": {"href": f"{base}/ancestors"},
        }
        if self.parent_id:
            links["parent"] = {
                "href": f"/v1/vocabularies/{self.vocabulary_id}/terms/{self.parent_id}"
            }
        return links


# ---------------------------------------------------------------------------
# Primary record types (shared base)
# ---------------------------------------------------------------------------

class RecordBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    status: str = "draft"
    metadata_: dict[str, Any] = {}


class ObjectCreate(RecordBase):
    idno: str | None = None
    object_type: str | None = None
    collection_status: str = "active"


class RecordRead(RecordBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    version: int

    _api_path: ClassVar[str]
    _record_type: ClassVar[str]

    @computed_field(alias="_links")
    def links(self) -> dict[str, dict[str, str]]:
        base = f"/v1/{self._api_path}/{self.id}"
        links = {
            "self": {"href": base},
            "relations": {
                "href": f"/v1/relations?from_type={self._record_type}&from_id={self.id}"
            },
        }
        if self._record_type == "object":
            links["media"] = {"href": f"{base}/media"}
        return links


class ObjectRead(ObjectCreate, RecordRead):
    _api_path: ClassVar[str] = "objects"
    _record_type: ClassVar[str] = "object"


class EntityCreate(RecordBase):
    idno: str | None = None
    entity_type: str | None = None


class EntityRead(EntityCreate, RecordRead):
    _api_path: ClassVar[str] = "entities"
    _record_type: ClassVar[str] = "entity"


class PlaceCreate(RecordBase):
    idno: str | None = None
    place_type: str | None = None
    lat: float | None = None
    lon: float | None = None


class PlaceRead(PlaceCreate, RecordRead):
    _api_path: ClassVar[str] = "places"
    _record_type: ClassVar[str] = "place"


class OccurrenceCreate(RecordBase):
    idno: str | None = None
    occurrence_type: str | None = None


class OccurrenceRead(OccurrenceCreate, RecordRead):
    _api_path: ClassVar[str] = "occurrences"
    _record_type: ClassVar[str] = "occurrence"


class ProcedureCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    idno: str | None = None
    procedure_type: str
    status: str = "draft"
    start_date: date | None = None
    end_date: date | None = None
    due_date: date | None = None
    reference_number: str | None = None
    metadata_: dict[str, Any] = {}


class ProcedureRead(ProcedureCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    version: int


class ProcedureComplete(BaseModel):
    collection_status: str | None = None


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------

class RelationCreate(BaseModel):
    from_type: str
    from_id: uuid.UUID
    to_type: str
    to_id: uuid.UUID
    relation_type: str
    metadata_: dict[str, Any] = {}


class RelationUpdate(BaseModel):
    relation_type: str | None = None
    metadata_: dict[str, Any] | None = None


class RelationRead(RelationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_schema_derived: bool = False
    created_at: datetime


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

PermissionAction = Literal["read", "create", "update", "delete"]
PermissionRole = Literal["admin", "editor", "cataloger", "viewer"]

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = "viewer"

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Passwort muss Buchstaben und Zahlen enthalten")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    onboarding_completed_at: datetime | None = None
    last_login_at: datetime | None = None


class RolePermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: PermissionRole
    record_type: Literal["object", "entity", "place", "occurrence", "procedure"]
    action: PermissionAction


class RolePermissionUpdate(BaseModel):
    permissions: list[RolePermissionRead]


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Passwort muss Buchstaben und Zahlen enthalten")
        return value


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Passwort muss Buchstaben und Zahlen enthalten")
        return value


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("Passwort muss Buchstaben und Zahlen enthalten")
        return value


class EmailChange(BaseModel):
    new_email: EmailStr
    current_password: str


class OnboardingUpdate(BaseModel):
    completed: bool


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
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: uuid.UUID
    role: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# OAI Sets
# ---------------------------------------------------------------------------

class OAISetCreate(BaseModel):
    set_spec: str
    set_name: str
    filter_record_type: str | None = None
    filter_q: str | None = None
    filter_status: str | None = None
    filter_metadata: dict[str, Any] = {}


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
    items: list[Any]


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
    changed_fields: dict[str, Any]
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
    snapshot: dict[str, Any]
    created_by: uuid.UUID | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Batch editing
# ---------------------------------------------------------------------------

BatchOperationType = Literal[
    "set_status",
    "set_field",
    "append_field",
    "clear_field",
    "add_relation",
    "remove_relation",
]


class BatchSetStatus(BaseModel):
    type: Literal["set_status"]
    value: str


class BatchSetField(BaseModel):
    type: Literal["set_field"]
    field: str
    value: Any


class BatchAppendField(BaseModel):
    type: Literal["append_field"]
    field: str
    value: Any


class BatchClearField(BaseModel):
    type: Literal["clear_field"]
    field: str


class BatchAddRelation(BaseModel):
    type: Literal["add_relation"]
    relation_to_type: str
    relation_to_id: uuid.UUID
    relation_type: str


class BatchRemoveRelation(BaseModel):
    type: Literal["remove_relation"]
    relation_to_type: str
    relation_to_id: uuid.UUID
    relation_type: str


BatchOperation = Annotated[
    BatchSetStatus
    | BatchSetField
    | BatchAppendField
    | BatchClearField
    | BatchAddRelation
    | BatchRemoveRelation,
    Field(discriminator="type"),
]


class BatchRequest(BaseModel):
    operation: BatchOperation
    ids: list[uuid.UUID] | None = None
    filters: dict[str, Any] | None = None

    @field_validator("filters")
    @classmethod
    def _validate_filters(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is not None and not isinstance(v, dict):
            raise ValueError("filters muss ein Objekt sein.")
        return v

    @field_validator("ids")
    @classmethod
    def _validate_ids(cls, v: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        if v is not None and not isinstance(v, list):
            raise ValueError("ids muss eine Liste sein.")
        return v

    @model_validator(mode="after")
    def _exactly_one_selector(self) -> "BatchRequest":
        has_ids = bool(self.ids)
        has_filters = bool(self.filters)
        if has_ids and has_filters:
            raise ValueError("Nur einer der Parameter ids oder filters darf angegeben werden.")
        if not has_ids and not has_filters:
            raise ValueError("Entweder ids oder filters muss angegeben werden.")
        return self


class BatchResponse(BaseModel):
    affected: int
    errors: list[str] = []
    batch_job_id: uuid.UUID | None = None
    task_id: str | None = None
