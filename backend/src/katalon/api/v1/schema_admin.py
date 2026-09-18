# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import copy
import json
import re
import uuid
from collections import defaultdict
from typing import Any, cast

import yaml
from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import CursorResult, func, or_, select, update
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import AuthoritySource, FieldDefinition, Vocabulary, VocabularyTerm
from katalon.core.schemas import FieldDefinitionCreate, FieldDefinitionRead
from katalon.services import authority_service
from katalon.services.pid_service import PID_PROVIDERS, available_pid_providers
from katalon.services.schema_ai_service import schema_chat
from katalon.services.subtype_service import ensure_subtype_exists

SCHEMA_TARGET_TYPES = {
    "object",
    "entity",
    "place",
    "occurrence",
    "procedure",
    "collection",
    "storage_location",
    "vocabulary_term",
}
VOCABULARY_TERM_FIELD_TYPES = {"text", "number", "boolean", "authority"}


def _validate_schema_target_type(target_type: str) -> None:
    if target_type not in SCHEMA_TARGET_TYPES:
        raise HTTPException(status_code=422, detail="Ungültiger Primärtyp.")


async def _ensure_schema_subtype_exists(db: DBDep, target_type: str, subtype: str | None) -> None:
    if target_type == "vocabulary_term":
        if not subtype:
            raise HTTPException(status_code=422, detail="Vokabular ist erforderlich.")
        try:
            vocab_id = uuid.UUID(subtype)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Ungültige Vokabular-ID.") from exc
        if not await db.get(Vocabulary, vocab_id):
            raise HTTPException(status_code=422, detail="Vokabular nicht gefunden.")
        return
    await ensure_subtype_exists(db, target_type, subtype)


async def _validate_unique_detail_role(
    db: DBDep, data: FieldDefinitionCreate, exclude_id: uuid.UUID | None
) -> None:
    if data.detail_role == "none":
        return
    conflict_query = select(FieldDefinition.id).where(
        FieldDefinition.target_type == data.target_type,
        (
            FieldDefinition.target_subtype.is_(None)
            if data.target_subtype is None
            else FieldDefinition.target_subtype == data.target_subtype
        ),
        FieldDefinition.detail_role == data.detail_role,
        FieldDefinition.is_deleted.is_(False),
    )
    if exclude_id is not None:
        conflict_query = conflict_query.where(FieldDefinition.id != exclude_id)
    if await db.scalar(conflict_query.limit(1)) is not None:
        raise HTTPException(
            status_code=422,
            detail=f"Es gibt bereits ein Feld mit der Rolle '{data.detail_role}' für diesen Typ/Subtyp.",
        )


async def _check_field_name_collision(
    db: DBDep,
    *,
    target_type: str,
    target_subtype: str | None,
    parent_id: uuid.UUID | None,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    conditions = [
        FieldDefinition.target_type == target_type,
        FieldDefinition.name == name,
        FieldDefinition.is_deleted.is_(False),
    ]
    if parent_id is not None:
        conditions.append(FieldDefinition.parent_id == parent_id)
    else:
        conditions.append(FieldDefinition.parent_id.is_(None))
        if target_subtype is None:
            conditions.append(FieldDefinition.target_subtype.is_(None))
        else:
            conditions.append(FieldDefinition.target_subtype == target_subtype)

    if exclude_id is not None:
        conditions.append(FieldDefinition.id != exclude_id)

    existing = await db.scalar(select(FieldDefinition.id).where(*conditions).limit(1))
    if existing is not None:
        detail = (
            "Ein Unterfeld mit diesem internen Namen existiert bereits in dieser Gruppe."
            if parent_id is not None
            else "Ein Feld mit diesem internen Namen existiert bereits für diesen Typ/Subtyp."
        )
        raise HTTPException(status_code=409, detail=detail)


async def _validate_field_settings(
    db: DBDep, data: FieldDefinitionCreate, existing: FieldDefinition | None = None
) -> None:
    for setting_name in ("validation_regex", "pattern"):
        pattern = data.settings.get(setting_name)
        if pattern is None:
            continue
        if not isinstance(pattern, str):
            raise HTTPException(
                status_code=422,
                detail=f"'{setting_name}' muss ein regulärer Ausdruck als Text sein.",
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Ungültiger regulärer Ausdruck für '{setting_name}': {exc}.",
            ) from exc

    if data.target_type == "vocabulary_term" and data.field_type not in VOCABULARY_TERM_FIELD_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Dieser Feldtyp ist für Vokabularterme nicht erlaubt.",
        )

    if data.field_type == "group" and not data.is_repeatable:
        raise HTTPException(
            status_code=422,
            detail="Containerfelder (Gruppe) sind immer wiederholbar; Werte werden als Array gespeichert.",
        )

    if data.is_translatable:
        if data.is_repeatable:
            raise HTTPException(
                status_code=422,
                detail="Übersetzbare Felder können nicht wiederholbar sein.",
            )
        if data.field_type not in {"text", "richtext"}:
            raise HTTPException(
                status_code=422,
                detail="Nur Text- und Rich-Text-Felder können übersetzbar sein.",
            )
        if data.parent_id:
            raise HTTPException(
                status_code=422,
                detail="Unterfelder von Containerfeldern können nicht übersetzbar sein.",
            )

    if data.field_type == "pid":
        provider = data.settings.get("pid_provider")
        if provider is not None and provider not in PID_PROVIDERS:
            raise HTTPException(
                status_code=422,
                detail=f"Unbekannter PID-Provider. Erlaubt: {', '.join(PID_PROVIDERS)}.",
            )
        current_provider = (existing.settings or {}).get("pid_provider") if existing else None
        if provider not in available_pid_providers() and provider != current_provider:
            raise HTTPException(
                status_code=422,
                detail="Dieser PID-Provider ist nicht vollständig konfiguriert.",
            )

    if data.field_type == "authority":
        source = data.settings.get("source")
        unchanged = existing is not None and source == (existing.settings or {}).get("source")
        if not unchanged:
            db_sources = list((await db.execute(select(AuthoritySource))).scalars().all())
            enabled = (
                {item.id for item in db_sources if item.is_enabled}
                if db_sources
                else set(authority_service.list_sources())
            )
            if source not in enabled:
                raise HTTPException(
                    status_code=422,
                    detail="Unbekannte oder deaktivierte Authority-Quelle.",
                )

    vocab_id = data.settings.get("vocabulary_id")
    expected_kind = "term"
    if data.field_type == "relation":
        vocab_id = data.settings.get("relation_type_vocab")
        expected_kind = "relation"
        if not vocab_id:
            raise HTTPException(
                status_code=422,
                detail="Ein Relationsfeld benötigt ein Relationstyp-Vokabular.",
            )
    if not vocab_id:
        return
    try:
        vocab = await db.get(Vocabulary, uuid.UUID(str(vocab_id)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Ungültige Vokabular-ID.") from exc
    if not vocab or vocab.kind != expected_kind:
        raise HTTPException(
            status_code=422,
            detail=f"Vokabular muss vom Typ '{expected_kind}' sein.",
        )
    fixed_relation_type = data.settings.get("fixed_relation_type")
    if data.field_type == "relation":
        target_type = data.settings.get("target_type")
        matching_terms = select(VocabularyTerm.id).where(
            VocabularyTerm.vocabulary_id == vocab.id,
            (VocabularyTerm.applies_from == [])
            | VocabularyTerm.applies_from.contains([data.target_type]),
            (VocabularyTerm.applies_to == []) | VocabularyTerm.applies_to.contains([target_type]),
        )
        if fixed_relation_type:
            matching_terms = matching_terms.where(VocabularyTerm.term == fixed_relation_type)
        if await db.scalar(matching_terms.limit(1)) is None:
            if fixed_relation_type:
                detail = "Der feste Relationstyp ist für Quell- und Zieltyp nicht erlaubt."
            else:
                detail = "Das Relationstyp-Vokabular enthält keinen Typ für diese Quell- und Zieltypkombination."
            raise HTTPException(status_code=422, detail=detail)


def _fd_read(
    f: FieldDefinition, children: list[FieldDefinitionRead] | None = None
) -> FieldDefinitionRead:
    """Validate a FieldDefinition ORM object into FieldDefinitionRead without triggering lazy loads."""
    cols = {attr.key: getattr(f, attr.key) for attr in sa_inspect(type(f)).mapper.column_attrs}
    cols["children"] = children or []
    return FieldDefinitionRead.model_validate(cols)


router = APIRouter(prefix="/schema", tags=["schema"])


def _enqueue_reindex(db: DBDep, target_type: str) -> None:
    """Defer a type-specific ES reindex until ``db`` commits (#392).

    Saving several facet/visibility checkboxes at once (see #settings/facetten)
    issues one PUT per changed field, each calling this. bulk_reindex_type_task
    always rebuilds from current DB state regardless of which field triggered
    it, so firing it N times back-to-back only multiplies wall-clock time on
    a large collection without changing the result. Coalesce same-type bursts
    into a single job via a short-lived Redis claim; on any Redis hiccup, fail
    open and enqueue anyway — duplicate work beats a silently skipped reindex.
    """
    if target_type == "vocabulary_term":
        return
    from katalon.workers.enqueue import after_commit
    from katalon.workers.index_tasks import bulk_reindex_type_task

    if not _claim_reindex_trigger(target_type):
        return
    after_commit(db, bulk_reindex_type_task, target_type)


def _claim_reindex_trigger(target_type: str, window_seconds: int = 10) -> bool:
    """True if this call should enqueue; False if another call for the same
    type already claimed the window (and will pick up this change too)."""
    try:
        import redis as redis_lib

        from katalon.config import settings

        client = redis_lib.from_url(settings.redis_url)
        return bool(
            client.set(f"katalon:reindex:trigger:{target_type}", "1", nx=True, ex=window_seconds)
        )
    except Exception:
        return True


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str]
    fields: list[FieldDefinitionRead]


class SchemaAiAssistMessage(BaseModel):
    role: str
    content: str


class SchemaAiAssistRequest(BaseModel):
    target_type: str
    target_subtype: str | None = None
    messages: list[SchemaAiAssistMessage]


class SchemaAiAssistResponse(BaseModel):
    reply: str
    proposal: dict[str, Any] | None = None
    usage: dict[str, int]


class SchemaResetSummary(BaseModel):
    deletable_fields: int


class SchemaResetResult(SchemaResetSummary):
    deleted_fields: int


async def _embed_children(
    db: DBDep, target_type: str, top_fields: list[FieldDefinition], include_deleted: bool = False
) -> list[FieldDefinitionRead]:
    """Load sub-fields for all group fields and embed them as children."""
    group_ids = [f.id for f in top_fields if f.field_type == "group"]
    children_map: dict[uuid.UUID, list[FieldDefinition]] = defaultdict(list[Any])
    if group_ids:
        sub_query = select(FieldDefinition).where(
            FieldDefinition.target_type == target_type,
            FieldDefinition.parent_id.in_(group_ids),
        )
        if not include_deleted:
            sub_query = sub_query.where(FieldDefinition.is_deleted.is_(False))
        sub_result = await db.execute(sub_query.order_by(FieldDefinition.sort_order))
        for sf in sub_result.scalars().all():
            if sf.parent_id is not None:
                children_map[sf.parent_id].append(sf)

    out: list[FieldDefinitionRead] = []
    for f in top_fields:
        children = (
            [_fd_read(c) for c in children_map.get(f.id, [])] if f.field_type == "group" else []
        )
        out.append(_fd_read(f, children))
    return out


@router.get(
    "/{target_type}",
    response_model=list[FieldDefinitionRead],
    summary="List field definitions for a target type",
    responses={422: {"description": "Invalid target type or subtype"}},
)
async def list_fields(
    target_type: str,
    db: DBDep,
    subtype: str | None = Query(default=None, description="Filter to generic + this subtype"),
    include_deleted: bool = Query(False, description="Include soft-deleted fields"),
) -> list[FieldDefinitionRead]:
    _validate_schema_target_type(target_type)
    if subtype is not None:
        await _ensure_schema_subtype_exists(db, target_type, subtype)
    q = select(FieldDefinition).where(
        FieldDefinition.target_type == target_type,
        FieldDefinition.parent_id.is_(None),  # top-level only; sub-fields embedded via children
    )
    if subtype:
        q = q.where(
            or_(FieldDefinition.target_subtype.is_(None), FieldDefinition.target_subtype == subtype)
        )
    if not include_deleted:
        q = q.where(FieldDefinition.is_deleted.is_(False))
    result = await db.execute(q.order_by(FieldDefinition.sort_order))
    top_fields = list(result.scalars().all())
    return await _embed_children(db, target_type, top_fields, include_deleted=include_deleted)


@router.get(
    "/{target_type}/reset-summary",
    response_model=SchemaResetSummary,
    dependencies=[require_role("admin")],
    summary="Count field definitions that a schema reset would soft-delete",
)
async def schema_reset_summary(
    target_type: str, db: DBDep, subtype: str | None = Query(default=None)
) -> SchemaResetSummary:
    _validate_schema_target_type(target_type)
    if subtype is not None:
        await _ensure_schema_subtype_exists(db, target_type, subtype)
    conditions = [
        FieldDefinition.target_type == target_type,
        FieldDefinition.name.notin_(["label", "idno"]),
        FieldDefinition.is_deleted.is_(False),
    ]
    if subtype is not None:
        conditions.append(FieldDefinition.target_subtype == subtype)
    deletable_fields = await db.scalar(
        select(func.count()).select_from(FieldDefinition).where(*conditions)
    )
    return SchemaResetSummary(deletable_fields=deletable_fields or 0)


@router.post(
    "/{target_type}/reset",
    response_model=SchemaResetResult,
    dependencies=[require_role("admin")],
    summary="Soft-delete all custom field definitions for a target type",
)
async def reset_schema(
    target_type: str, db: DBDep, subtype: str | None = Query(default=None)
) -> SchemaResetResult:
    _validate_schema_target_type(target_type)
    if subtype is not None:
        await _ensure_schema_subtype_exists(db, target_type, subtype)
    conditions = [
        FieldDefinition.target_type == target_type,
        FieldDefinition.name.notin_(["label", "idno"]),
        FieldDefinition.is_deleted.is_(False),
    ]
    if subtype is not None:
        conditions.append(FieldDefinition.target_subtype == subtype)
    result = await db.execute(update(FieldDefinition).where(*conditions).values(is_deleted=True))
    deleted_fields = cast("CursorResult[Any]", result).rowcount or 0
    await db.flush()
    _enqueue_reindex(db, target_type)
    return SchemaResetResult(deletable_fields=deleted_fields, deleted_fields=deleted_fields)


async def _validate_parent(db: DBDep, parent_id: uuid.UUID, field_type: str) -> None:
    """Validate parent_id: parent must exist, be a group field, and sub-fields cannot be groups."""
    if field_type == "group":
        raise HTTPException(
            status_code=422,
            detail="Verschachtelte Containerfelder (Gruppe in Gruppe) sind nicht erlaubt.",
        )
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == parent_id,
            FieldDefinition.is_deleted.is_(False),
        )
    )
    parent = result.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="Übergeordnetes Feld nicht gefunden.")
    if parent.field_type != "group":
        raise HTTPException(
            status_code=422,
            detail="Sub-Felder können nur unter einem Containerfeld (Gruppe) angelegt werden.",
        )


@router.post(
    "",
    response_model=FieldDefinitionRead,
    status_code=201,
    dependencies=[require_role("admin")],
    summary="Create a new field definition",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Parent field not found"},
        422: {"description": "Invalid field name, target type, subtype, parent, or settings"},
    },
)
async def create_field(data: FieldDefinitionCreate, db: DBDep) -> FieldDefinitionRead:
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="Feldname darf nicht leer sein")
    # A field hidden from the detail view has no public display context to derive
    # a facet value from — never let is_facet survive with show_in_detail off,
    # regardless of what the client sent.
    if not data.show_in_detail:
        data.is_facet = False
    # Sub-fields (parent_id set) are embedded as `children` on their group field and are
    # never returned by the top-level schema.list() query the record list view reads from
    # (schema_admin.list_fields filters parent_id IS NULL) — show_in_list has no effect on
    # them, so never let it linger and imply a list column that will never render.
    if data.parent_id:
        data.show_in_list = False
    _validate_schema_target_type(data.target_type)
    if data.parent_id:
        await _validate_parent(db, data.parent_id, data.field_type)
    else:
        await _ensure_schema_subtype_exists(db, data.target_type, data.target_subtype)
    await _validate_field_settings(db, data)
    await _validate_unique_detail_role(db, data, exclude_id=None)
    await _check_field_name_collision(
        db,
        target_type=data.target_type,
        target_subtype=data.target_subtype,
        parent_id=data.parent_id,
        name=data.name,
    )

    # Soft-deleted Felder blockieren ihren Namen per Unique-Constraint. Statt zu kollidieren,
    # reaktiviere die alte Zeile (gleiche ID, gleiche Historie) und übernehme die neuen Werte.
    reused_conditions = [
        FieldDefinition.target_type == data.target_type,
        FieldDefinition.name == data.name,
        FieldDefinition.is_deleted.is_(True),
    ]
    if data.parent_id is not None:
        reused_conditions.append(FieldDefinition.parent_id == data.parent_id)
    else:
        reused_conditions.append(FieldDefinition.parent_id.is_(None))
        if data.target_subtype is None:
            reused_conditions.append(FieldDefinition.target_subtype.is_(None))
        else:
            reused_conditions.append(FieldDefinition.target_subtype == data.target_subtype)

    reused = await db.scalar(select(FieldDefinition).where(*reused_conditions))
    if reused is not None:
        for key, value in data.model_dump().items():
            setattr(reused, key, value)
        reused.is_deleted = False
        await db.flush()
        _enqueue_reindex(db, data.target_type)
        return _fd_read(reused)

    field = FieldDefinition(**data.model_dump())
    db.add(field)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Ein Feld mit diesem internen Namen existiert bereits für diesen Typ/Subtyp.",
        ) from exc
    _enqueue_reindex(db, data.target_type)
    return _fd_read(field)


@router.put(
    "/{field_id}",
    response_model=FieldDefinitionRead,
    dependencies=[require_role("admin")],
    summary="Update an existing field definition",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Field definition or parent field not found"},
        422: {"description": "Invalid field name, target type, subtype, parent, or settings"},
    },
)
async def update_field(
    field_id: uuid.UUID, data: FieldDefinitionCreate, db: DBDep, current_user: CurrentUser
) -> FieldDefinitionRead:
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="Feldname darf nicht leer sein")
    if not data.show_in_detail:
        data.is_facet = False
    if data.parent_id:
        data.show_in_list = False
    _validate_schema_target_type(data.target_type)
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(False)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    if data.parent_id:
        await _validate_parent(db, data.parent_id, data.field_type)
    else:
        await _ensure_schema_subtype_exists(db, data.target_type, data.target_subtype)
    await _validate_field_settings(db, data, field)
    await _validate_unique_detail_role(db, data, exclude_id=field_id)
    if (
        data.name != field.name
        or data.target_subtype != field.target_subtype
        or data.parent_id != field.parent_id
    ):
        await _check_field_name_collision(
            db,
            target_type=data.target_type,
            target_subtype=data.target_subtype,
            parent_id=data.parent_id,
            name=data.name,
            exclude_id=field.id,
        )
    old_is_public = field.is_public
    old_settings = field.settings or {}
    old_is_translatable = field.is_translatable
    old_is_repeatable = field.is_repeatable
    old_field_type = field.field_type
    for k, v in data.model_dump().items():
        setattr(field, k, v)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Ein Feld mit diesem internen Namen existiert bereits für diesen Typ/Subtyp.",
        ) from exc
    inherited_settings_changed = field.field_type == "relation" and any(
        old_settings.get(key) != field.settings.get(key)
        for key in ("target_type", "fixed_relation_type", "inherited_fields")
    )
    if old_is_translatable != field.is_translatable and not field.parent_id:
        # A field's is_translatable flag is reversible in both directions (#399):
        # existing records are reshaped in the same transaction so the schema and
        # the stored data never drift apart. Toggling on is lossless (wraps the
        # legacy plain-string value); toggling off is lossy (keeps only the
        # primary language) — the admin UI warns and asks for confirmation
        # before sending a downgrade, based on the field's usage count.
        from katalon.services.ai_service import get_admin_ai_config
        from katalon.services.schema_service import migrate_translatable_shape

        ai_config = await get_admin_ai_config(db)
        primary_language = (ai_config.supported_languages or ["de", "en"])[0]
        await migrate_translatable_shape(
            db,
            field,
            enable=field.is_translatable,
            primary_language=primary_language,
            user_id=current_user.id,
        )
        await db.flush()
    if old_is_repeatable != field.is_repeatable and not field.parent_id:
        # Same reversibility contract for is_repeatable (#399): scalar <-> list is
        # reshaped automatically. Enabling wraps the scalar in a single-item list
        # (lossless); disabling collapses to the first list entry — the admin UI
        # warns first when any affected record would actually lose entries.
        from katalon.services.schema_service import migrate_repeatable_shape

        await migrate_repeatable_shape(
            db, field, enable=field.is_repeatable, user_id=current_user.id
        )
        await db.flush()
    # is_facet toggles need no reindex: docs carry facet_all_* for every public
    # field and the portal whitelists aggregations against is_facet at query
    # time. Only content-affecting changes (visibility, inherited relation
    # settings, translatable/repeatable shape, field type) require a rebuild.
    if (
        field.is_public != old_is_public
        or inherited_settings_changed
        or old_is_translatable != field.is_translatable
        or old_is_repeatable != field.is_repeatable
        or old_field_type != field.field_type
    ):
        _enqueue_reindex(db, field.target_type)
    return _fd_read(field)


class FieldUsageResponse(BaseModel):
    field_id: uuid.UUID
    field_name: str
    target_type: str
    usage_count: int
    # Populated only when the matching `new_*` query param was supplied — the
    # frontend uses these to decide whether a pending schema change needs a
    # data-loss confirmation before it is sent (#399).
    repeatable_collapse_count: int | None = None
    type_change_risk_count: int | None = None


@router.get(
    "/{field_id}/usage",
    response_model=FieldUsageResponse,
    dependencies=[require_role("admin")],
    summary="Get record usage count for a field definition, optionally previewing the impact of a pending reconfiguration",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Field definition not found"},
    },
)
async def get_field_usage(
    field_id: uuid.UUID,
    db: DBDep,
    new_is_repeatable: bool | None = Query(
        default=None,
        description="If False and the field is currently repeatable, also returns repeatable_collapse_count.",
    ),
    new_field_type: str | None = Query(
        default=None,
        description="If different from the field's current type, also returns type_change_risk_count.",
    ),
) -> FieldUsageResponse:
    from katalon.services.schema_service import (
        count_field_type_change_risk,
        count_field_usage,
        count_repeatable_collapse_loss,
    )

    result = await db.execute(
        select(FieldDefinition).where(FieldDefinition.id == field_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    usage_count = await count_field_usage(db, field)
    repeatable_collapse_count = (
        await count_repeatable_collapse_loss(db, field)
        if new_is_repeatable is False and field.is_repeatable
        else None
    )
    type_change_risk_count = (
        await count_field_type_change_risk(db, field, new_field_type)
        if new_field_type is not None and new_field_type != field.field_type
        else None
    )
    return FieldUsageResponse(
        field_id=field.id,
        field_name=field.name,
        target_type=field.target_type,
        usage_count=usage_count,
        repeatable_collapse_count=repeatable_collapse_count,
        type_change_risk_count=type_change_risk_count,
    )


@router.delete(
    "/{field_id}",
    status_code=204,
    dependencies=[require_role("admin")],
    summary="Soft-delete a field definition",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Field definition not found"},
        422: {"description": "Field 'label'/'idno' is a system field and cannot be deleted"},
    },
)
async def delete_field(
    field_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
    purge_data: bool = Query(
        default=False,
        description="If True, also deletes all values for this field from existing records.",
    ),
) -> None:
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(False)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    if field.name in ("label", "idno"):
        raise HTTPException(
            status_code=422,
            detail=f"Das Feld '{field.name}' ist ein Systemfeld und kann nicht gelöscht werden.",
        )
    field.is_deleted = True
    if field.field_type == "group":
        await db.execute(
            update(FieldDefinition)
            .where(FieldDefinition.parent_id == field.id)
            .values(is_deleted=True)
        )
    target_type = field.target_type

    if purge_data:
        from katalon.services.schema_service import purge_field_data

        await purge_field_data(db, field, user_id=current_user.id)

    await db.flush()
    _enqueue_reindex(db, target_type)



@router.post(
    "/{field_id}/restore",
    response_model=FieldDefinitionRead,
    dependencies=[require_role("admin")],
    summary="Restore a soft-deleted field definition",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Deleted field definition not found"},
        422: {"description": "Parent group field is deleted or detail_role conflict"},
    },
)
async def restore_field(
    field_id: uuid.UUID,
    db: DBDep,
    restore_children: bool = Query(
        default=True, description="If True and field is a group, also restores its subfields"
    ),
) -> FieldDefinitionRead:
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(True)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Gelöschte Felddefinition nicht gefunden")

    # If field is a sub-field, verify its parent group exists and is active
    if field.parent_id is not None:
        parent = await db.get(FieldDefinition, field.parent_id)
        if not parent or parent.is_deleted:
            parent_name = parent.name if parent else ""
            raise HTTPException(
                status_code=422,
                detail=f"Das übergeordnete Feld '{parent_name}' ist gelöscht. Bitte stellen Sie zuerst das übergeordnete Feld wieder her.",
            )

    # Validate detail role uniqueness against active fields
    await _validate_unique_detail_role(db, field, exclude_id=field.id)

    # Validate field name collision against active fields
    await _check_field_name_collision(
        db,
        target_type=field.target_type,
        target_subtype=field.target_subtype,
        parent_id=field.parent_id,
        name=field.name,
        exclude_id=field.id,
    )

    field.is_deleted = False

    # If group field, re-activate children
    if field.field_type == "group" and restore_children:
        await db.execute(
            update(FieldDefinition)
            .where(FieldDefinition.parent_id == field.id)
            .values(is_deleted=False)
        )

    target_type = field.target_type
    await db.flush()
    _enqueue_reindex(db, target_type)

    children_reads = []
    if field.field_type == "group":
        sub_res = await db.execute(
            select(FieldDefinition)
            .where(
                FieldDefinition.target_type == target_type,
                FieldDefinition.parent_id == field.id,
                FieldDefinition.is_deleted.is_(False),
            )
            .order_by(FieldDefinition.sort_order)
        )
        children_reads = [_fd_read(c) for c in sub_res.scalars().all()]

    return _fd_read(field, children=children_reads)


@router.delete(
    "/{field_id}/hard",
    status_code=204,
    dependencies=[require_role("admin")],
    summary="Permanently hard-delete a field definition",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Field definition not found"},
        409: {"description": "Field is still in use by existing records"},
        422: {"description": "System fields cannot be deleted"},
    },
)
async def hard_delete_field(field_id: uuid.UUID, db: DBDep) -> None:
    from katalon.services.schema_service import count_field_usage

    result = await db.execute(select(FieldDefinition).where(FieldDefinition.id == field_id))
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    if field.name in ("label", "idno"):
        raise HTTPException(
            status_code=422,
            detail=f"Das Feld '{field.name}' ist ein Systemfeld und kann nicht endgültig gelöscht werden.",
        )

    usage_count = await count_field_usage(db, field)
    if usage_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Feld kann nicht endgültig gelöscht werden: Es wird noch in {usage_count} Datensätzen verwendet. Bitte bereinigen Sie die Felddaten zuerst.",
        )

    if field.field_type == "group":
        sub_res = await db.execute(
            select(FieldDefinition).where(FieldDefinition.parent_id == field.id)
        )
        for sf in sub_res.scalars().all():
            sub_usage = await count_field_usage(db, sf)
            if sub_usage > 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"Feldgruppe kann nicht endgültig gelöscht werden: Das Unterfeld '{sf.name}' wird noch in {sub_usage} Datensätzen verwendet.",
                )

    target_type = field.target_type
    await db.delete(field)
    await db.flush()
    _enqueue_reindex(db, target_type)


@router.post(
    "/{field_id}/duplicate",
    response_model=FieldDefinitionRead,
    status_code=201,
    dependencies=[require_role("admin")],
    summary="Duplicate a field definition including sub-fields if group",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Field definition not found"},
    },
)
async def duplicate_field(field_id: uuid.UUID, db: DBDep) -> FieldDefinitionRead:
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(False)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")

    all_names_result = await db.execute(
        select(FieldDefinition.name).where(
            FieldDefinition.target_type == field.target_type,
            (
                FieldDefinition.target_subtype.is_(None)
                if field.target_subtype is None
                else FieldDefinition.target_subtype == field.target_subtype
            ),
        )
    )
    used_names = set(all_names_result.scalars().all())

    def _next_unique_name(base: str, used: set[str]) -> str:
        candidate = f"{base}_copy"
        counter = 2
        while candidate in used:
            candidate = f"{base}_copy_{counter}"
            counter += 1
        used.add(candidate)
        return candidate

    new_name = _next_unique_name(field.name, used_names)

    new_label = dict(field.label or {})
    if new_label.get("de"):
        new_label["de"] = f"{new_label['de']} (Kopie)"
    elif "de" not in new_label:
        new_label["de"] = f"{field.name} (Kopie)"

    if new_label.get("en"):
        new_label["en"] = f"{new_label['en']} (Copy)"
    elif "en" not in new_label:
        new_label["en"] = f"{field.name} (Copy)"

    for lang, val in list(new_label.items()):
        if lang not in ("de", "en") and isinstance(val, str) and val:
            new_label[lang] = f"{val} (Copy)"

    max_sort = await db.scalar(
        select(func.coalesce(func.max(FieldDefinition.sort_order), 0)).where(
            FieldDefinition.target_type == field.target_type,
            (
                FieldDefinition.target_subtype.is_(None)
                if field.target_subtype is None
                else FieldDefinition.target_subtype == field.target_subtype
            ),
            (
                FieldDefinition.parent_id.is_(None)
                if field.parent_id is None
                else FieldDefinition.parent_id == field.parent_id
            ),
        )
    )
    new_sort_order = max(field.sort_order + 1, (max_sort or 0) + 1)

    new_field = FieldDefinition(
        target_type=field.target_type,
        target_subtype=field.target_subtype,
        name=new_name,
        label=new_label,
        help_text=copy.deepcopy(field.help_text or {}),
        field_type=field.field_type,
        is_required=field.is_required,
        is_repeatable=field.is_repeatable,
        is_translatable=field.is_translatable,
        is_searchable=field.is_searchable,
        sort_order=new_sort_order,
        settings=copy.deepcopy(field.settings or {}),
        show_in_detail=field.show_in_detail,
        show_in_list=field.show_in_list,
        detail_slot=field.detail_slot,
        detail_role="none" if field.detail_role == "description" else field.detail_role,
        is_public=field.is_public,
        is_facet=field.is_facet,
        parent_id=field.parent_id,
    )
    db.add(new_field)
    await db.flush()

    cloned_children: list[FieldDefinition] = []
    if field.field_type == "group":
        children_result = await db.execute(
            select(FieldDefinition)
            .where(
                FieldDefinition.parent_id == field.id,
                FieldDefinition.is_deleted.is_(False),
            )
            .order_by(FieldDefinition.sort_order)
        )
        original_children = list(children_result.scalars().all())
        for child in original_children:
            child_name = _next_unique_name(child.name, used_names)
            child_label = dict(child.label or {})
            if child_label.get("de"):
                child_label["de"] = f"{child_label['de']} (Kopie)"
            if child_label.get("en"):
                child_label["en"] = f"{child_label['en']} (Copy)"
            new_child = FieldDefinition(
                target_type=child.target_type,
                target_subtype=child.target_subtype,
                name=child_name,
                label=child_label,
                help_text=copy.deepcopy(child.help_text or {}),
                field_type=child.field_type,
                is_required=child.is_required,
                is_repeatable=child.is_repeatable,
                is_translatable=child.is_translatable,
                is_searchable=child.is_searchable,
                sort_order=child.sort_order,
                settings=copy.deepcopy(child.settings or {}),
                show_in_detail=child.show_in_detail,
                show_in_list=child.show_in_list,
                detail_slot=child.detail_slot,
                detail_role="none" if child.detail_role == "description" else child.detail_role,
                is_public=child.is_public,
                is_facet=child.is_facet,
                parent_id=new_field.id,
            )
            db.add(new_child)
            cloned_children.append(new_child)
        await db.flush()

    _enqueue_reindex(db, field.target_type)
    children_read = [_fd_read(c) for c in cloned_children] if field.field_type == "group" else []
    return _fd_read(new_field, children_read)


@router.post(
    "/import",
    response_model=ImportResult,
    status_code=200,
    dependencies=[require_role("admin")],
    summary="Import field definitions from a YAML or JSON file",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "File could not be parsed or has an invalid format"},
    },
)
async def import_schema(
    file: UploadFile,
    db: DBDep,
    dry_run: bool = Query(False, description="Preview changes without writing to DB"),
    overwrite: bool = Query(False, description="Overwrite existing fields"),
) -> ImportResult:
    """Import field definitions from a YAML or JSON file.

    Expected format:
      target_type: object
      fields:
        - name: title
          label: {de: Titel, en: Title}
          field_type: text
          is_required: true
    """
    content = await file.read()
    try:
        filename = file.filename or ""
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Datei konnte nicht geparst werden: {exc}")

    if not isinstance(data, dict) or "target_type" not in data or "fields" not in data:
        raise HTTPException(
            status_code=422,
            detail="Ungültiges Format. Erwartet: {target_type, fields: [...]}",
        )

    target_type: str = data["target_type"]
    _validate_schema_target_type(target_type)
    raw_fields: list[Any] = data.get("fields", [])

    if not isinstance(raw_fields, list):
        raise HTTPException(status_code=422, detail="'fields' muss eine Liste sein")

    # Load existing fields (by target_type + name) for upsert logic
    existing_result = await db.execute(
        select(FieldDefinition).where(FieldDefinition.target_type == target_type)
    )
    existing_map: dict[tuple[str | None, str], FieldDefinition] = {
        (f.target_subtype, f.name): f for f in existing_result.scalars().all()
    }

    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    result_fields: list[FieldDefinition] = []

    for idx, raw in enumerate(raw_fields):
        if not isinstance(raw, dict):
            errors.append(f"Feld #{idx}: kein Objekt")
            continue
        name = raw.get("name", "").strip()
        if not name:
            errors.append(f"Feld #{idx}: 'name' fehlt oder leer")
            continue

        field_data = FieldDefinitionCreate(
            target_type=target_type,
            target_subtype=raw.get("target_subtype"),
            name=name,
            label=raw.get("label", {}),
            help_text=raw.get("help_text", {}),
            field_type=raw.get("field_type", "text"),
            is_required=raw.get("is_required", False),
            is_repeatable=raw.get("is_repeatable", False),
            sort_order=raw.get("sort_order", idx),
            settings=raw.get("settings", {}),
        )
        await _ensure_schema_subtype_exists(db, target_type, field_data.target_subtype)
        await _validate_field_settings(db, field_data)

        key = (field_data.target_subtype, name)
        if key in existing_map:
            existing = existing_map[key]
            if not overwrite:
                skipped += 1
                result_fields.append(existing)
                continue
            if not dry_run:
                for k, v in field_data.model_dump().items():
                    setattr(existing, k, v)
                existing.is_deleted = False
            updated += 1
            result_fields.append(existing)
        else:
            field = FieldDefinition(**field_data.model_dump())
            if not dry_run:
                db.add(field)
                await db.flush()
            created += 1
            result_fields.append(field)

    if not dry_run and (created > 0 or updated > 0):
        await db.flush()
        _enqueue_reindex(db, target_type)

    return ImportResult(
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        fields=[_fd_read(f) for f in result_fields],
    )


@router.post(
    "/ai-assist",
    response_model=SchemaAiAssistResponse,
    dependencies=[require_role("admin")],
    summary="Chat with the AI schema assistant to draft new field definitions",
    responses={
        403: {"description": "Insufficient permissions"},
        409: {"description": "AI assistance disabled or not fully configured"},
        422: {"description": "Invalid target type/subtype or malformed AI response"},
        429: {"description": "AI token usage limit exceeded"},
        502: {"description": "AI provider request failed"},
    },
)
async def ai_assist_schema(
    data: SchemaAiAssistRequest, db: DBDep, current_user: CurrentUser
) -> SchemaAiAssistResponse:
    _validate_schema_target_type(data.target_type)
    if data.target_subtype is not None:
        await _ensure_schema_subtype_exists(db, data.target_type, data.target_subtype)
    result = await schema_chat(
        db,
        user_id=current_user.id,
        target_type=data.target_type,
        subtype=data.target_subtype,
        messages=[m.model_dump() for m in data.messages],
    )
    return SchemaAiAssistResponse.model_validate(result)
