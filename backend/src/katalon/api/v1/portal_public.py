# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any, ClassVar

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, computed_field
from sqlalchemy import and_, exists, func, or_, select

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
from katalon.config import settings
from katalon.core.dependencies import DBDep, OptionalCurrentUser
from katalon.core.limiter import limiter
from katalon.core.models import (
    Banner,
    Collection,
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
from katalon.services import relation_service, search_service
from katalon.services.advanced_search_service import AdvancedQuery, resolve_query

router = APIRouter(tags=["portal"])
_PUBLIC_TYPES = ("object", "entity", "place", "occurrence", "collection")
_SORT_OPTIONS = {"idno_asc", "title_asc", "newest", "oldest"}
_PORTAL_STAFF_ROLES = {"superuser", "admin", "editor", "cataloger", "viewer"}
_MODELS: dict[
    str, type[Object] | type[Entity] | type[Place] | type[Occurrence] | type[Collection]
] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "collection": Collection,
}


def _staff_user(user: User | None) -> User | None:
    """Keep future public accounts on the anonymous portal projection."""
    return user if user and user.role in _PORTAL_STAFF_ROLES else None


async def _filter_facet_names(
    db: DBDep, facet_names: list[str] | None, target_types: tuple[str, ...] | list[str]
) -> list[str] | None:
    """Whitelist requested facet names against is_facet field definitions.

    Index docs carry facet_all_* for every public field, so without this gate
    anonymous callers could aggregate any public field. Only fields explicitly
    marked is_facet (plus portal-configured inherited/relation facets) may be
    aggregated; unknown names are dropped, not rejected.
    """
    from katalon.integrations.elasticsearch import RELATED_FACET_NAMES

    if not facet_names:
        return None
    special = {n for n in facet_names if n in RELATED_FACET_NAMES or n.startswith("inherited_")}
    direct = [n for n in facet_names if n not in special]
    allowed = set(special)
    if direct:
        rows = await db.execute(
            select(FieldDefinition.name).where(
                FieldDefinition.is_facet.is_(True),
                FieldDefinition.is_deleted.is_(False),
                FieldDefinition.target_type.in_(target_types),
                FieldDefinition.name.in_(direct),
            )
        )
        configured = {row[0] for row in rows.all()}
        allowed.update(n for n in direct if n in configured)
    return sorted(allowed)


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


class PortalCollectionRead(PortalRecordRead):
    _api_path: ClassVar[str] = "collections"
    _record_type: ClassVar[str] = "collection"

    collection_type: str | None = None
    parent_id: uuid.UUID | None = None


class PortalCollectionHierarchyItem(BaseModel):
    id: uuid.UUID
    idno: str | None
    collection_type: str | None
    title: str | None = None
    parent_id: uuid.UUID | None = None


class PortalCollectionDetail(PortalCollectionRead):
    parent: PortalCollectionHierarchyItem | None = None
    ancestors: list[PortalCollectionHierarchyItem] = []
    children: list[PortalCollectionHierarchyItem] = []
    member_objects_count: int = 0


class PortalCollectionPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PortalCollectionRead]


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
    from_label: str | None = None
    to_label: str | None = None


class PortalFieldDefinitionRead(BaseModel):
    name: str
    label: dict[str, Any]
    field_type: str
    is_repeatable: bool
    is_searchable: bool
    is_facet: bool
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
    relation_filters: dict[str, list[str]] = Field(default_factory=dict)
    status: list[str] = Field(default_factory=list)
    sort: str | None = None


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
    uri: str | None = None
    exact_match_uris: list[str] = []

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
    return await objects.list_objects(
        db, _staff_user(current_user), page, page_size, None, object_type, q
    )


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


@router.get("/collections", response_model=PortalCollectionPage)
async def list_collections(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    parent_id: uuid.UUID | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    staff_user = _staff_user(current_user)
    query = select(Collection).where(Collection.deleted_at.is_(None))
    if staff_user is None:
        query = query.where(Collection.status.in_(PUBLIC_STATUSES))
    if parent_id is not None:
        query = query.where(Collection.parent_id == parent_id)
    if q:
        from sqlalchemy import Text, cast

        query = query.where(
            Collection.idno.icontains(q, autoescape=True)
            | cast(Collection.metadata_, Text).icontains(q, autoescape=True)
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = (
        query.order_by(Collection.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = (await db.execute(query)).scalars().all()
    response_items: list[PortalCollectionRead] = []
    for col in items:
        metadata = col.metadata_ or {}
        if staff_user is None:
            from katalon.services.public_metadata_service import (
                filter_public_metadata,
                load_public_fields,
            )

            pub_fields = await load_public_fields(db, "collection")
            metadata = filter_public_metadata(metadata, pub_fields, col.collection_type)
        response_items.append(
            PortalCollectionRead(
                id=col.id,
                idno=col.idno,
                status=col.status,
                collection_type=col.collection_type,
                parent_id=col.parent_id,
                metadata_=metadata,
                created_at=col.created_at,
                updated_at=col.updated_at,
            )
        )
    return {"total": total, "page": page, "page_size": page_size, "items": response_items}


@router.get("/collections/{collection_id}", response_model=PortalCollectionDetail)
async def get_collection(
    collection_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser
) -> PortalCollectionDetail:
    staff_user = _staff_user(current_user)
    query = select(Collection).where(
        Collection.id == collection_id, Collection.deleted_at.is_(None)
    )
    if staff_user is None:
        query = query.where(Collection.status.in_(PUBLIC_STATUSES))
    result = await db.execute(query)
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")

    metadata = col.metadata_ or {}
    if staff_user is None:
        from katalon.services.public_metadata_service import (
            filter_public_metadata,
            load_public_fields,
        )

        pub_fields = await load_public_fields(db, "collection")
        metadata = filter_public_metadata(metadata, pub_fields, col.collection_type)

    from katalon.services.search_service import _extract_title

    ancestors: list[PortalCollectionHierarchyItem] = []
    curr_parent_id = col.parent_id
    visited: set[uuid.UUID] = {col.id}
    parent_item: PortalCollectionHierarchyItem | None = None
    while curr_parent_id is not None and curr_parent_id not in visited:
        visited.add(curr_parent_id)
        p_query = select(Collection).where(
            Collection.id == curr_parent_id, Collection.deleted_at.is_(None)
        )
        if staff_user is None:
            p_query = p_query.where(Collection.status.in_(PUBLIC_STATUSES))
        p_col = (await db.execute(p_query)).scalar_one_or_none()
        if not p_col:
            break
        title = _extract_title(p_col.metadata_ or {}) or p_col.idno or str(p_col.id)[:8]
        ancestor_item = PortalCollectionHierarchyItem(
            id=p_col.id,
            idno=p_col.idno,
            collection_type=p_col.collection_type,
            title=title,
            parent_id=p_col.parent_id,
        )
        ancestors.insert(0, ancestor_item)
        if parent_item is None:
            parent_item = ancestor_item
        curr_parent_id = p_col.parent_id

    # Resolve immediate public child collections
    c_query = select(Collection).where(
        Collection.parent_id == col.id, Collection.deleted_at.is_(None)
    )
    if staff_user is None:
        c_query = c_query.where(Collection.status.in_(PUBLIC_STATUSES))
    children_cols = (
        (await db.execute(c_query.order_by(Collection.created_at.asc()))).scalars().all()
    )
    children_items = [
        PortalCollectionHierarchyItem(
            id=c.id,
            idno=c.idno,
            collection_type=c.collection_type,
            title=_extract_title(c.metadata_ or {}) or c.idno or str(c.id)[:8],
            parent_id=c.parent_id,
        )
        for c in children_cols
    ]

    # Count linked member objects
    member_count_stmt = select(func.count(Relation.id)).where(
        Relation.to_type == "collection",
        Relation.to_id == col.id,
        Relation.from_type == "object",
    )
    member_objects_count = (await db.execute(member_count_stmt)).scalar_one() or 0

    return PortalCollectionDetail(
        id=col.id,
        idno=col.idno,
        status=col.status,
        collection_type=col.collection_type,
        parent_id=col.parent_id,
        metadata_=metadata,
        created_at=col.created_at,
        updated_at=col.updated_at,
        parent=parent_item,
        ancestors=ancestors,
        children=children_items,
        member_objects_count=member_objects_count,
    )


@router.get("/objects/{object_id}/media", response_model=list[PortalMediaRead])
async def list_media(
    object_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser
) -> list[dict[str, Any]]:
    items = await media.list_media(object_id, db, _staff_user(current_user))
    return [{**item, "object_id": object_id} for item in items]


@router.get("/objects/{object_id}/media/{media_id}/file")
async def serve_media_file(
    object_id: uuid.UUID, media_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser
) -> FileResponse:
    return await media.serve_media_file(object_id, media_id, db, _staff_user(current_user))


@router.get("/objects/{object_id}/media/{media_id}/thumbnail")
async def serve_media_thumbnail(
    object_id: uuid.UUID, media_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser
) -> RedirectResponse:
    return await media.serve_media_thumbnail(object_id, media_id, db, _staff_user(current_user))


@router.get("/objects/{object_id}/iiif/manifest")
async def iiif_manifest(
    object_id: uuid.UUID, db: DBDep, request: Request, current_user: OptionalCurrentUser
) -> dict[str, Any]:
    return await objects.iiif_manifest(object_id, db, request, _staff_user(current_user))


def _public_endpoint_clause(type_column: Any, id_column: Any) -> Any:
    clauses = []
    for record_type, model in _MODELS.items():
        conditions = [
            model.id == id_column,
            model.status.in_(PUBLIC_STATUSES),
            model.deleted_at.is_(None),
        ]
        clauses.append(
            and_(type_column == record_type, exists(select(model.id).where(*conditions)))
        )
    return or_(*clauses)


@router.get("/relations", response_model=list[PortalRelationRead])
async def list_relations(
    db: DBDep,
    from_type: str | None = None,
    from_id: uuid.UUID | None = None,
    to_type: str | None = None,
    to_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    include_subcollections: bool = False,
) -> list[PortalRelationRead]:
    query = select(Relation).where(
        _public_endpoint_clause(Relation.from_type, Relation.from_id),
        _public_endpoint_clause(Relation.to_type, Relation.to_id),
    )
    if from_type:
        if from_type not in _PUBLIC_TYPES:
            return []
        query = query.where(Relation.from_type == from_type)
    if from_id:
        if from_type == "collection" and include_subcollections:
            from katalon.services.collection_service import get_collection_subtree_ids

            subtree_ids = await get_collection_subtree_ids(db, from_id, public_only=True)
            query = query.where(Relation.from_id.in_(subtree_ids))
        else:
            query = query.where(Relation.from_id == from_id)
    if to_type:
        if to_type not in _PUBLIC_TYPES:
            return []
        query = query.where(Relation.to_type == to_type)
    if to_id:
        if to_type == "collection" and include_subcollections:
            from katalon.services.collection_service import get_collection_subtree_ids

            subtree_ids = await get_collection_subtree_ids(db, to_id, public_only=True)
            query = query.where(Relation.to_id.in_(subtree_ids))
        else:
            query = query.where(Relation.to_id == to_id)
    query = query.limit(limit)
    relations = (await db.execute(query)).scalars().all()
    labels = await relation_service.resolve_relation_labels(db, relations, public_only=True)
    return [
        PortalRelationRead(
            id=rel.id,
            from_type=rel.from_type,
            from_id=rel.from_id,
            to_type=rel.to_type,
            to_id=rel.to_id,
            relation_type=rel.relation_type,
            from_label=labels.get((rel.from_type, rel.from_id)),
            to_label=labels.get((rel.to_type, rel.to_id)),
        )
        for rel in relations
    ]


@router.get("/search", response_model=SearchResponse)
@limiter.limit(lambda: settings.rate_limit_public_search)
async def search(
    request: Request,
    db: DBDep,
    current_user: OptionalCurrentUser,
    q: str | None = None,
    type: str | None = None,
    status: list[str] | None = Query(None),
    facets: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rel_entity: list[str] | None = Query(None),
    rel_place: list[str] | None = Query(None),
    rel_occurrence: list[str] | None = Query(None),
    rel_collection: list[str] | None = Query(None),
    sort: str | None = None,
) -> SearchResponse:
    staff_user = _staff_user(current_user)
    if type and type not in _PUBLIC_TYPES:
        raise HTTPException(status_code=422, detail="Ungültiger öffentlicher Record-Typ.")
    if sort and sort not in _SORT_OPTIONS:
        raise HTTPException(status_code=422, detail="Ungültige Sortierung.")
    extra_filters = {
        key[5:]: [value for value in request.query_params.getlist(key) if value]
        for key in request.query_params.keys()
        if key.startswith("meta_")
    }
    rel_filters: dict[str, list[str]] = {
        key: values
        for key, values in {
            "related_entities": rel_entity,
            "related_places": rel_place,
            "related_occurrences": rel_occurrence,
            "related_collections": rel_collection,
        }.items()
        if values
    }
    if rel_collection:
        from katalon.services.collection_service import get_collection_subtree_titles

        sub_titles: list[str] = []
        for collection_id in rel_collection:
            sub_titles.extend(
                await get_collection_subtree_titles(db, collection_id, public_only=True)
            )
        rel_filters["related_collections"] = sub_titles
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
        status_facet=status if staff_user is not None else None,
        page=page,
        page_size=page_size,
        extra_filters=extra_filters or None,
        numeric_filters=numeric_filters or None,
        facet_fields=await _filter_facet_names(
            db,
            [field.strip() for field in facets.split(",") if field.strip()] if facets else None,
            (type,) if type else _PUBLIC_TYPES,
        ),
        rel_filters=rel_filters or None,
        subtitle_fields=(portal_config.subtitle_fields if portal_config else None) or None,
        facet_sort=(portal_config.facet_sort if portal_config else None) or "count",
        sort=sort,
    )
    return SearchResponse(**result)


@router.post("/search/advanced", response_model=SearchResponse)
@limiter.limit(lambda: settings.rate_limit_public_search)
async def advanced_search(
    request: Request,
    data: AdvancedSearchRequest,
    db: DBDep,
    current_user: OptionalCurrentUser,
) -> SearchResponse:
    staff_user = _staff_user(current_user)
    if data.sort and data.sort not in _SORT_OPTIONS:
        raise HTTPException(status_code=422, detail="Ungültige Sortierung.")
    try:
        advanced_filter = await resolve_query(db, data.query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    allowed_relation_filters = {
        key: value
        for key, value in data.relation_filters.items()
        if key
        in {"related_entities", "related_places", "related_occurrences", "related_collections"}
        and value
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
        status_facet=data.status if staff_user is not None else None,
        page=data.page,
        page_size=data.page_size,
        extra_filters=data.metadata_filters or None,
        numeric_filters=numeric_filters or None,
        facet_fields=await _filter_facet_names(
            db,
            data.facet_fields,
            (data.query.record_type,) if data.query.record_type else _PUBLIC_TYPES,
        ),
        rel_filters=allowed_relation_filters or None,
        subtitle_fields=(portal_config.subtitle_fields if portal_config else None) or None,
        advanced_filter=advanced_filter,
        facet_sort=(portal_config.facet_sort if portal_config else None) or "count",
        sort=data.sort,
    )
    return SearchResponse(**result)


@router.get("/schema/{target_type}", response_model=list[PortalFieldDefinitionRead])
async def list_fields(
    target_type: str, db: DBDep, response: Response, current_user: OptionalCurrentUser
) -> list[FieldDefinition]:
    if target_type not in _PUBLIC_TYPES:
        raise HTTPException(status_code=404, detail="Schema nicht gefunden")

    query = select(FieldDefinition).where(
        FieldDefinition.target_type == target_type,
        FieldDefinition.is_deleted.is_(False),
    )
    staff_user = _staff_user(current_user)
    if staff_user is None:
        query = query.where(FieldDefinition.is_public.is_(True))
        # Anonymous projection only — the staff variant additionally contains
        # non-public fields and must never land in a shared cache.
        response.headers["Cache-Control"] = _CONFIG_CACHE
        response.headers["Vary"] = "Authorization"
    else:
        response.headers["Cache-Control"] = "private, no-store"
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
        select(VocabularyTerm)
        .where(VocabularyTerm.vocabulary_id == vocab_id)
        .order_by(VocabularyTerm.term)
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


# Diese Antworten lädt das Portal bei jedem Seitenaufruf erneut und sie ändern
# sich praktisch nie. Eine kurze TTL nimmt genau die Requests aus der Kette,
# die Crawler-Traffic vervielfacht, ohne dass Redaktionsänderungen spürbar
# verzögert sichtbar werden.
_CONFIG_CACHE = "public, max-age=60"


@router.get("/portal/config", response_model=portal.PortalConfigRead)
async def get_portal_config(db: DBDep, response: Response) -> portal.PortalConfigRead:
    config = await portal.get_portal_config(db)
    if config.logo_url == "/v1/portal/logo/file":
        config.logo_url = "/portal/v1/portal/logo/file"
    response.headers["Cache-Control"] = _CONFIG_CACHE
    return config


@router.get("/portal/logo/file")
async def serve_logo() -> FileResponse:
    return await portal.serve_logo()


@router.get("/pages", response_model=list[pages.PageRead])
async def list_pages(db: DBDep, response: Response) -> list[StaticPage]:
    response.headers["Cache-Control"] = _CONFIG_CACHE
    return await pages.list_pages(db)


@router.get("/pages/{slug}", response_model=pages.PageRead)
async def get_page(slug: str, db: DBDep) -> StaticPage:
    return await pages.get_page(slug, db)


@router.get("/banners/active/portal", response_model=list[banners.BannerRead])
async def active_portal_banners(db: DBDep, response: Response) -> list[Banner]:
    response.headers["Cache-Control"] = _CONFIG_CACHE
    return await banners.active_portal_banners(db)


@router.get("/theme")
async def get_theme() -> JSONResponse:
    result = await theme.get_theme()
    result.headers["Cache-Control"] = _CONFIG_CACHE
    return result
