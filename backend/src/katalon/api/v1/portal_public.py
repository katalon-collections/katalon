from __future__ import annotations

import uuid
from datetime import datetime
from typing import ClassVar

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, computed_field
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
from katalon.api.v1.search import SearchResponse
from katalon.core.dependencies import DBDep
from katalon.core.limiter import limiter
from katalon.core.models import (
    Entity,
    Object,
    Occurrence,
    Place,
    Relation,
    Vocabulary,
    VocabularyTerm,
)
from katalon.core.visibility import PUBLIC_STATUSES
from katalon.services import search_service

router = APIRouter(tags=["portal"])
_PUBLIC_TYPES = ("object", "entity", "place", "occurrence")
_MODELS = {"object": Object, "entity": Entity, "place": Place, "occurrence": Occurrence}


class PortalRecordRead(BaseModel):
    """Explicit public projection; never expose ORM-only fields such as version/search_vector."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    idno: str | None
    status: str
    metadata_: dict
    created_at: datetime
    updated_at: datetime

    _api_path: ClassVar[str]
    _record_type: ClassVar[str]

    @computed_field(alias="_links")
    @property
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
    rights_holder: dict | None
    created_at: datetime

    @computed_field(alias="_links")
    @property
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
    label: dict
    field_type: str
    settings: dict
    show_in_detail: bool


class PortalVocabularyRead(BaseModel):
    """Public vocabulary projection; links point to the anonymous portal API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_hierarchical: bool
    kind: str

    @computed_field(alias="_links")
    @property
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
    label: dict
    inverse_label: dict
    metadata_: dict
    parent_id: uuid.UUID | None
    applies_from: list[str]
    applies_to: list[str]

    @computed_field(alias="_links")
    @property
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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    object_type: str | None = None,
    q: str | None = None,
) -> PortalObjectPage:
    return await objects.list_objects(db, None, page, page_size, None, object_type, q)


@router.get("/objects/{object_id}", response_model=PortalObjectRead)
async def get_object(object_id: uuid.UUID, db: DBDep) -> Object:
    return await objects.get_object(object_id, db, None)


@router.get("/entities/{entity_id}", response_model=PortalEntityRead)
async def get_entity(entity_id: uuid.UUID, db: DBDep) -> Entity:
    return await entities.get_entity(entity_id, db, None)


@router.get("/places/{place_id}", response_model=PortalPlaceRead)
async def get_place(place_id: uuid.UUID, db: DBDep) -> Place:
    return await places.get_place(place_id, db, None)


@router.get("/occurrences/{occurrence_id}", response_model=PortalOccurrenceRead)
async def get_occurrence(occurrence_id: uuid.UUID, db: DBDep) -> Occurrence:
    return await occurrences.get_occurrence(occurrence_id, db, None)


@router.get("/objects/{object_id}/media", response_model=list[PortalMediaRead])
async def list_media(object_id: uuid.UUID, db: DBDep) -> list[dict]:
    items = await media.list_media(object_id, db, None)
    return [{**item, "object_id": object_id} for item in items]


@router.get("/objects/{object_id}/media/{media_id}/file")
async def serve_media_file(object_id: uuid.UUID, media_id: uuid.UUID, db: DBDep):
    return await media.serve_media_file(object_id, media_id, db, None)


@router.get("/objects/{object_id}/iiif/manifest")
async def iiif_manifest(object_id: uuid.UUID, db: DBDep, request: Request) -> dict:
    return await objects.iiif_manifest(object_id, db, request, portal_only=True)


def _public_endpoint_clause(type_column, id_column):
    clauses = []
    for record_type, model in _MODELS.items():
        conditions = [model.id == id_column, model.status.in_(PUBLIC_STATUSES)]
        if model is Object:
            conditions.append(model.collection_status == "active")
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
    q: str | None = None,
    type: str | None = None,
    facets: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rel_entity: str | None = None,
    rel_place: str | None = None,
    rel_occurrence: str | None = None,
) -> SearchResponse:
    if type and type not in _PUBLIC_TYPES:
        raise HTTPException(status_code=422, detail="Ungültiger öffentlicher Record-Typ.")
    extra_filters = {k[5:]: v for k, v in request.query_params.items() if k.startswith("meta_") and v}
    rel_filters = {
        key: value
        for key, value in {
            "related_entities": rel_entity,
            "related_places": rel_place,
            "related_occurrences": rel_occurrence,
        }.items()
        if value
    }
    result = await search_service.search(
        query=q,
        record_type=type,
        record_types=None if type else _PUBLIC_TYPES,
        status="public",
        page=page,
        page_size=page_size,
        extra_filters=extra_filters or None,
        facet_fields=[field.strip() for field in facets.split(",") if field.strip()] if facets else None,
        rel_filters=rel_filters or None,
        active_objects_only=True,
    )
    return SearchResponse(**result)


@router.get("/schema/{target_type}", response_model=list[PortalFieldDefinitionRead])
async def list_fields(target_type: str, db: DBDep):
    if target_type not in _PUBLIC_TYPES:
        raise HTTPException(status_code=404, detail="Schema nicht gefunden")
    from katalon.core.models import FieldDefinition

    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == target_type,
            FieldDefinition.is_deleted.is_(False),
        ).order_by(FieldDefinition.sort_order)
    )
    return list(result.scalars().all())


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
async def serve_logo():
    return await portal.serve_logo()


@router.get("/pages", response_model=list[pages.PageRead])
async def list_pages(db: DBDep):
    return await pages.list_pages(db)


@router.get("/pages/{slug}", response_model=pages.PageRead)
async def get_page(slug: str, db: DBDep):
    return await pages.get_page(slug, db)


@router.get("/banners/active/portal", response_model=list[banners.BannerRead])
async def active_portal_banners(db: DBDep):
    return await banners.active_portal_banners(db)


@router.get("/theme")
async def get_theme():
    return await theme.get_theme()
