from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any, ClassVar

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, computed_field
from sqlalchemy import and_, exists, or_, select

from katalon.api.v1 import (
    banners,
    entities,
    media,
    objects,
    occurrences,
    pages,
    places,
    portal,
    theme,
)
from katalon.api.v1.search import SearchResponse, _range_filters
from katalon.core.dependencies import DBDep, OptionalCurrentUser
from katalon.core.limiter import limiter
from katalon.core.models import (
    Banner,
    Entity,
    FieldDefinition,
    Object,
    Occurrence,
    Place,
    PortalConfig,
    Relation,
    StaticPage,
    User,
    Vocabulary,
    VocabularyTerm,
)
from katalon.core.schemas import EntityRead, ObjectRead, OccurrenceRead, PlaceRead
from katalon.core.visibility import PUBLIC_STATUSES
from katalon.services import search_service
from katalon.services.advanced_search_service import AdvancedQuery, resolve_query

router = APIRouter(tags=["portal"])
_PUBLIC_TYPES = ("object", "entity", "place", "occurrence")
_PORTAL_STAFF_ROLES = {"superuser", "admin", "editor", "cataloger", "viewer"}
_MODELS: dict[str, type[Object] | type[Entity] | type[Place] | type[Occurrence]] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
}


def _staff_user(user: User | None) -> User | None:
    """Keep future public accounts on the anonymous portal projection."""
    return user if user and user.role in _PORTAL_STAFF_ROLES else None


class PortalRecordRead(BaseModel):
    """Explicit public projection; never expose ORM-only fields such as version."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    idno: str | None
    status: str
    metadata_: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    _api_path: ClassVar[str]
    _record_type: ClassVar[str]

    @computed_field(alias="_links")
    def links(self) -> dict[str, dict[str, str]]:
        base = f"/portal/v1/{self._api_path}/{self.id}"
        links = {
            "self": {"href": base},
            "relations": {
                "href": f"/portal/v1/relations?from_type={self._record_type}&from_id={self.id}"
            },
        }
        if self._record_type == "object":
            links["media"] = {"href": f"{base}/media"}
        return links


class PortalObjectRead(PortalRecordRead):
    _api_path: ClassVar[str] = "objects"
    _record_type: ClassVar[str] = "object"

    object_type: str | None
    collection_status: str


class PortalEntityRead(PortalRecordRead):
    _api_path: ClassVar[str] = "entities"
    _record_type: ClassVar[str] = "entity"

    entity_type: str | None


class PortalPlaceRead(PortalRecordRead):
    _api_path: ClassVar[str] = "places"
    _record_type: ClassVar[str] = "place"

    place_type: str | None
    lat: float | None = None
    lon: float | None = None


class PortalOccurrenceRead(PortalRecordRead):
    _api_path: ClassVar[str] = "occurrences"
    _record_type: ClassVar[str] = "occurrence"

    occurrence_type: str | None


class PortalObjectPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PortalObjectRead]


class PortalMediaRead(BaseModel):
    id: str
    object_id: uuid.UUID
    filename: str
    mime_type: str
    category: str
    status: str
    is_primary: bool
    media_type: str | None
    license_uri: str | None
    rights_holder: dict[str, Any] | None
    created_at: datetime

    @computed_field(alias="_links")
    def links(self) -> dict[str, dict[str, str]]:
        links = {
            "object": {"href": f"/portal/v1/objects/{self.object_id}"},
            "file": {"href": f"/portal/v1/objects/{self.object_id}/media/{self.id}/file"},
        }
        if self.license_uri and media._is_absolute_http_url(self.license_uri):
            links["license"] = {"href": self.license_uri}
        return links


class PortalRelationRead(BaseModel):
    id: uuid.UUID
    from_type: str
    from_id: uuid.UUID
    to_type: str
    to_id: uuid.UUID
    relation_type: str


class PortalFieldDefinitionRead(BaseModel):
    name: str
    label: dict[str, Any]
    field_type: str
    is_repeatable: bool
    is_searchable: bool
    parent_id: uuid.UUID | None
    settings: dict[str, Any]
    show_in_detail: bool
    detail_slot: str
    detail_role: str


class PortalSearchTermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    term: str
    label: dict[str, Any]
    parent_id: uuid.UUID | None


class NumericRange(BaseModel):
    from_: float | None = Field(default=None, alias="from")
    to: float | None = None


class AdvancedSearchRequest(BaseModel):
    query: AdvancedQuery
    q: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    facet_fields: list[str] = Field(default_factory=list, max_length=100)
    metadata_filters: dict[str, list[str]] = Field(default_factory=dict)
    numeric_filters: dict[str, NumericRange] = Field(default_factory=dict)
    relation_filters: dict[str, str] = Field(default_factory=dict)


class PortalVocabularyRead(BaseModel):
    """Public vocabulary projection; links point to the anonymous portal API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_hierarchical: bool
    kind: str

    @computed_field(alias="_links")
    def links(self) -> dict[str, dict[str, str]]:
        base = f"/portal/v1/vocabularies/{self.id}"
        return {
            "self": {"href": base},
            "terms": {"href": f"{base}/terms"},
        }


class PortalVocabularyTermRead(BaseModel):
    """Public vocabulary-term projection; links point to the anonymous portal API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    vocabulary_id: uuid.UUID
    term: str
    label: dict[str, Any]
    inverse_label: dict[str, Any]
    metadata_: dict[str, Any]
    parent_id: uuid.UUID | None
    applies_from: list[str]
    applies_to: list[str]

    @computed_field(alias="_links")
    def links(self) -> dict[str, dict[str, str]]:
        base = f"/portal/v1/vocabularies/{self.vocabulary_id}/terms/{self.id}"
        links = {
            "self": {"href": base},
            "vocabulary": {"href": f"/portal/v1/vocabularies/{self.vocabulary_id}"},
        }
        if self.parent_id:
            links["parent"] = {
                "href": f"/portal/v1/vocabularies/{self.vocabulary_id}/terms/{self.parent_id}"
            }
        return links


@router.get("/objects", response_model=PortalObjectPage)
async def list_objects(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    object_type: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    return await objects.list_objects(db, _staff_user(current_user), page, page_size, None, object_type, q)


@router.get("/objects/{object_id}", response_model=PortalObjectRead)
async def get_object(
    object_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser
) -> Object | ObjectRead:
    return await objects.get_object(object_id, db, _staff_user(current_user))


@router.get("/entities/{entity_id}", response_model=PortalEntityRead)
async def get_entity(
    entity_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser
) -> Entity | EntityRead:
    return await entities.get_entity(entity_id, db, _staff_user(current_user))


@router.get("/places/{place_id}", response_model=PortalPlaceRead)
async def get_place(
    place_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser
) -> Place | PlaceRead:
    return await places.get_place(place_id, db, _staff_user(current_user))


@router.get("/occurrences/{occurrence_id}", response_model=PortalOccurrenceRead)
async def get_occurrence(
    occurrence_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser
) -> Occurrence | OccurrenceRead:
    return await occurrences.get_occurrence(occurrence_id, db, _staff_user(current_user))


@router.get("/objects/{object_id}/media", response_model=list[PortalMediaRead])
async def list_media(object_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser) -> list[dict[str, Any]]:
    items = await media.list_media(object_id, db, _staff_user(current_user))
    return [{**item, "object_id": object_id} for item in items]


@router.get("/objects/{object_id}/media/{media_id}/file")
async def serve_media_file(object_id: uuid.UUID, media_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser) -> FileResponse:
    return await media.serve_media_file(object_id, media_id, db, _staff_user(current_user))


@router.get("/objects/{object_id}/media/{media_id}/thumbnail")
async def serve_media_thumbnail(object_id: uuid.UUID, media_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser) -> RedirectResponse:
    return await media.serve_media_thumbnail(object_id, media_id, db, _staff_user(current_user))


@router.get("/objects/{object_id}/iiif/manifest")
async def iiif_manifest(object_id: uuid.UUID, db: DBDep, request: Request, current_user: OptionalCurrentUser) -> dict[str, Any]:
    return await objects.iiif_manifest(object_id, db, request, _staff_user(current_user))


def _public_endpoint_clause(type_column: Any, id_column: Any) -> Any:
    clauses = []
    for record_type, model in _MODELS.items():
        conditions = [
            model.id == id_column,
            model.status.in_(PUBLIC_STATUSES),
            model.deleted_at.is_(None),
        ]
        clauses.append(and_(type_column == record_type, exists(select(model.id).where(*conditions))))
    return or_(*clauses)


@router.get("/relations", response_model=list[PortalRelationRead])
async def list_relations(
    db: DBDep,
    from_type: str | None = None,
    from_id: uuid.UUID | None = None,
    to_type: str | None = None,
    to_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[Relation]:
    query = select(Relation).where(
        _public_endpoint_clause(Relation.from_type, Relation.from_id),
        _public_endpoint_clause(Relation.to_type, Relation.to_id),
    )
    if from_type:
        if from_type not in _PUBLIC_TYPES:
            return []
        query = query.where(Relation.from_type == from_type)
    if from_id:
        query = query.where(Relation.from_id == from_id)
    if to_type:
        if to_type not in _PUBLIC_TYPES:
            return []
        query = query.where(Relation.to_type == to_type)
    if to_id:
        query = query.where(Relation.to_id == to_id)
    return list((await db.execute(query.order_by(Relation.created_at.desc()).limit(limit))).scalars().all())


@router.get("/search", response_model=SearchResponse)
@limiter.limit("100/minute")
async def search(
    request: Request,
    db: DBDep,
    current_user: OptionalCurrentUser,
    q: str | None = None,
    type: str | None = None,
    facets: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rel_entity: str | None = None,
    rel_place: str | None = None,
    rel_occurrence: str | None = None,
) -> SearchResponse:
    staff_user = _staff_user(current_user)
    if type and type not in _PUBLIC_TYPES:
        raise HTTPException(status_code=422, detail="Ungültiger öffentlicher Record-Typ.")
    extra_filters = {
        key[5:]: [value for value in request.query_params.getlist(key) if value]
        for key in request.query_params.keys()
        if key.startswith("meta_")
    }
    rel_filters = {
        key: value
        for key, value in {
            "related_entities": rel_entity,
            "related_places": rel_place,
            "related_occurrences": rel_occurrence,
        }.items()
        if value
    }
    portal_config = (
        await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
    ).scalar_one_or_none()
    try:
        numeric_filters = _range_filters(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await search_service.search(
        query=q,
        record_type=type,
        record_types=None if type else _PUBLIC_TYPES,
        status="public" if staff_user is None else None,
        page=page,
        page_size=page_size,
        extra_filters=extra_filters or None,
        numeric_filters=numeric_filters or None,
        facet_fields=[field.strip() for field in facets.split(",") if field.strip()] if facets else None,
        rel_filters=rel_filters or None,
        subtitle_fields=(portal_config.subtitle_fields if portal_config else None) or None,
        facet_sort=(portal_config.facet_sort if portal_config else None) or "count",
    )
    return SearchResponse(**result)


@router.post("/search/advanced", response_model=SearchResponse)
@limiter.limit("100/minute")
async def advanced_search(
    request: Request,
    data: AdvancedSearchRequest,
    db: DBDep,
    current_user: OptionalCurrentUser,
) -> SearchResponse:
    staff_user = _staff_user(current_user)
    try:
        advanced_filter = await resolve_query(db, data.query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    allowed_relation_filters = {
        key: value
        for key, value in data.relation_filters.items()
        if key in {"related_entities", "related_places", "related_occurrences"} and value
    }
    portal_config = (
        await db.execute(select(PortalConfig).where(PortalConfig.key == "default"))
    ).scalar_one_or_none()
    numeric_filters = {
        field: (bounds.from_, bounds.to)
        for field, bounds in data.numeric_filters.items()
        if bounds.from_ is not None or bounds.to is not None
    }
    if any(
        not all(math.isfinite(value) for value in bounds if value is not None)
        or (bounds[0] is not None and bounds[1] is not None and bounds[0] > bounds[1])
        for bounds in numeric_filters.values()
    ):
        raise HTTPException(status_code=422, detail="Ungültiger Zahlenbereich.")
    result = await search_service.search(
        query=data.q,
        record_type=data.query.record_type,
        status="public" if staff_user is None else None,
        page=data.page,
        page_size=data.page_size,
        extra_filters=data.metadata_filters or None,
        numeric_filters=numeric_filters or None,
        facet_fields=data.facet_fields or None,
        rel_filters=allowed_relation_filters or None,
        subtitle_fields=(portal_config.subtitle_fields if portal_config else None) or None,
        advanced_filter=advanced_filter,
        facet_sort=(portal_config.facet_sort if portal_config else None) or "count",
    )
    return SearchResponse(**result)


@router.get("/schema/{target_type}", response_model=list[PortalFieldDefinitionRead])
async def list_fields(
    target_type: str, db: DBDep, current_user: OptionalCurrentUser
) -> list[FieldDefinition]:
    if target_type not in _PUBLIC_TYPES:
        raise HTTPException(status_code=404, detail="Schema nicht gefunden")

    query = select(FieldDefinition).where(
        FieldDefinition.target_type == target_type,
        FieldDefinition.is_deleted.is_(False),
    )
    if _staff_user(current_user) is None:
        query = query.where(FieldDefinition.is_public.is_(True))
    result = await db.execute(query.order_by(FieldDefinition.sort_order))
    return list(result.scalars().all())


@router.get(
    "/schema/{target_type}/fields/{field_name}/terms",
    response_model=list[PortalSearchTermRead],
)
async def list_search_field_terms(
    target_type: str, field_name: str, db: DBDep
) -> list[VocabularyTerm]:
    if target_type not in _PUBLIC_TYPES:
        raise HTTPException(status_code=404, detail="Suchfeld nicht gefunden")
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == target_type,
            FieldDefinition.name == field_name,
            FieldDefinition.field_type.in_(("vocab", "vocab_free")),
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.is_public.is_(True),
            FieldDefinition.is_searchable.is_(True),
            FieldDefinition.parent_id.is_(None),
        )
    )
    field = result.scalar_one_or_none()
    vocabulary_id = (field.settings or {}).get("vocabulary_id") if field else None
    try:
        vocabulary_uuid = uuid.UUID(str(vocabulary_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Suchfeld-Vokabular nicht gefunden") from None
    terms = await db.execute(
        select(VocabularyTerm)
        .where(VocabularyTerm.vocabulary_id == vocabulary_uuid)
        .order_by(VocabularyTerm.term)
    )
    return list(terms.scalars().all())


@router.get("/vocabularies", response_model=list[PortalVocabularyRead])
async def list_vocabularies(db: DBDep) -> list[Vocabulary]:
    result = await db.execute(select(Vocabulary).where(Vocabulary.name == "relation_types"))
    return list(result.scalars().all())


@router.get("/vocabularies/{vocab_id}", response_model=PortalVocabularyRead)
async def get_vocabulary(vocab_id: uuid.UUID, db: DBDep) -> Vocabulary:
    vocab = await db.get(Vocabulary, vocab_id)
    if vocab is None or vocab.name != "relation_types":
        raise HTTPException(status_code=404, detail="Vokabular nicht gefunden")
    return vocab


@router.get(
    "/vocabularies/{vocab_id}/terms",
    response_model=list[PortalVocabularyTermRead],
)
async def list_terms(vocab_id: uuid.UUID, db: DBDep) -> list[VocabularyTerm]:
    vocab = await db.get(Vocabulary, vocab_id)
    if vocab is None or vocab.name != "relation_types":
        raise HTTPException(status_code=404, detail="Vokabular nicht gefunden")
    result = await db.execute(
        select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab_id).order_by(VocabularyTerm.term)
    )
    return list(result.scalars().all())


@router.get(
    "/vocabularies/{vocab_id}/terms/{term_id}",
    response_model=PortalVocabularyTermRead,
)
async def get_term(vocab_id: uuid.UUID, term_id: uuid.UUID, db: DBDep) -> VocabularyTerm:
    term = await db.get(VocabularyTerm, term_id)
    if term is None or term.vocabulary_id != vocab_id:
        raise HTTPException(status_code=404, detail="Term nicht gefunden")
    vocab = await db.get(Vocabulary, vocab_id)
    if vocab is None or vocab.name != "relation_types":
        raise HTTPException(status_code=404, detail="Vokabular nicht gefunden")
    return term


@router.get("/portal/config", response_model=portal.PortalConfigRead)
async def get_portal_config(db: DBDep) -> portal.PortalConfigRead:
    config = await portal.get_portal_config(db)
    if config.logo_url == "/v1/portal/logo/file":
        config.logo_url = "/portal/v1/portal/logo/file"
    return config


@router.get("/portal/logo/file")
async def serve_logo() -> FileResponse:
    return await portal.serve_logo()


@router.get("/pages", response_model=list[pages.PageRead])
async def list_pages(db: DBDep) -> list[StaticPage]:
    return await pages.list_pages(db)


@router.get("/pages/{slug}", response_model=pages.PageRead)
async def get_page(slug: str, db: DBDep) -> StaticPage:
    return await pages.get_page(slug, db)


@router.get("/banners/active/portal", response_model=list[banners.BannerRead])
async def active_portal_banners(db: DBDep) -> list[Banner]:
    return await banners.active_portal_banners(db)


@router.get("/theme")
async def get_theme() -> JSONResponse:
    return await theme.get_theme()
