import uuid
from typing import Literal

from fastapi import APIRouter, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, text

from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import Vocabulary, VocabularyTerm
from katalon.core.schemas import (
    VocabularyCreate,
    VocabularyRead,
    VocabularyTermCreate,
    VocabularyTermRead,
)
from katalon.services import vocabulary_import_service
from katalon.services.schema_service import validate_metadata

router = APIRouter(prefix="/vocabularies", tags=["vocabularies"])


# ---------------------------------------------------------------------------
# Tree schema
# ---------------------------------------------------------------------------

class VocabularyTermNode(BaseModel):
    id: uuid.UUID
    term: str
    label: dict
    parent_id: uuid.UUID | None
    children: list["VocabularyTermNode"] = []

    model_config = {"from_attributes": True}


VocabularyTermNode.model_rebuild()


def _build_tree(terms: list[VocabularyTerm]) -> list[VocabularyTermNode]:
    """Convert a flat list of terms into a nested tree (root nodes only)."""
    by_id = {t.id: VocabularyTermNode(id=t.id, term=t.term, label=t.label, parent_id=t.parent_id) for t in terms}
    roots: list[VocabularyTermNode] = []
    for node in by_id.values():
        if node.parent_id and node.parent_id in by_id:
            by_id[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


# ---------------------------------------------------------------------------
# Vocabulary CRUD
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[VocabularyRead],
    summary="List all vocabularies",
)
async def list_vocabularies(db: DBDep) -> list[Vocabulary]:
    result = await db.execute(select(Vocabulary).order_by(Vocabulary.name))
    return list(result.scalars().all())


@router.post(
    "",
    response_model=VocabularyRead,
    status_code=201,
    dependencies=[require_role("admin")],
    summary="Create a new vocabulary",
    responses={
        403: {"description": "Insufficient permissions"},
    },
)
async def create_vocabulary(data: VocabularyCreate, db: DBDep) -> Vocabulary:
    vocab = Vocabulary(**data.model_dump())
    db.add(vocab)
    await db.commit()
    return vocab


# ---------------------------------------------------------------------------
# Terms – flat list
# ---------------------------------------------------------------------------

@router.get(
    "/{vocab_id}/terms",
    response_model=list[VocabularyTermRead],
    summary="List terms of a vocabulary, optionally filtered by search",
)
async def list_terms(
    vocab_id: uuid.UUID,
    db: DBDep,
    q: str | None = Query(None, description="Search term (filters by term or label)"),
    from_type: str | None = Query(None, description="Only terms allowed for this source record type"),
    to_type: str | None = Query(None, description="Only terms allowed for this target record type"),
) -> list[VocabularyTerm]:
    stmt = (
        select(VocabularyTerm)
        .where(VocabularyTerm.vocabulary_id == vocab_id)
        .order_by(VocabularyTerm.term)
    )
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            (VocabularyTerm.term.ilike(pattern))
            | (text("label::text ILIKE :pattern").bindparams(pattern=pattern))
        )
    if from_type:
        stmt = stmt.where(
            (VocabularyTerm.applies_from == text("'[]'::jsonb"))
            | (VocabularyTerm.applies_from.contains([from_type]))
        )
    if to_type:
        stmt = stmt.where(
            (VocabularyTerm.applies_to == text("'[]'::jsonb"))
            | (VocabularyTerm.applies_to.contains([to_type]))
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Terms – tree
# ---------------------------------------------------------------------------

@router.get(
    "/{vocab_id}/tree",
    response_model=list[VocabularyTermNode],
    summary="Get terms of a vocabulary as a nested tree",
    responses={
        404: {"description": "Vocabulary not found"},
    },
)
async def get_tree(vocab_id: uuid.UUID, db: DBDep) -> list[VocabularyTermNode]:
    """Return terms of a vocabulary as a nested tree.

    Root nodes are returned with their children recursively embedded.
    """
    vocab_result = await db.execute(select(Vocabulary).where(Vocabulary.id == vocab_id))
    if not vocab_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Vokabular nicht gefunden")

    result = await db.execute(
        select(VocabularyTerm)
        .where(VocabularyTerm.vocabulary_id == vocab_id)
        .order_by(VocabularyTerm.term)
    )
    terms = list(result.scalars().all())
    return _build_tree(terms)


@router.get(
    "/{vocab_id}/terms/{term_id}/ancestors",
    response_model=list[VocabularyTermRead],
    summary="Get the ancestor chain of a vocabulary term",
    responses={
        404: {"description": "Term not found"},
    },
)
async def get_ancestors(vocab_id: uuid.UUID, term_id: uuid.UUID, db: DBDep) -> list[VocabularyTerm]:
    """Return ancestor chain from root down to (not including) the given term."""
    result = await db.execute(
        select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab_id)
    )
    all_terms = {t.id: t for t in result.scalars().all()}

    term = all_terms.get(term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Term nicht gefunden")

    ancestors: list[VocabularyTerm] = []
    current = term
    seen: set[uuid.UUID] = set()
    while current.parent_id and current.parent_id not in seen:
        seen.add(current.id)
        parent = all_terms.get(current.parent_id)
        if not parent:
            break
        ancestors.insert(0, parent)
        current = parent

    return ancestors


# ---------------------------------------------------------------------------
# Term CRUD
# ---------------------------------------------------------------------------

@router.post(
    "/{vocab_id}/terms",
    response_model=VocabularyTermRead,
    status_code=201,
    dependencies=[require_role("admin")],
    summary="Create a new vocabulary term",
    responses={
        404: {"description": "Vocabulary not found"},
        422: {"description": "Metadata validation failed"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_term(
    vocab_id: uuid.UUID, data: VocabularyTermCreate, db: DBDep
) -> VocabularyTerm:
    vocab = await db.get(Vocabulary, vocab_id)
    if not vocab:
        raise HTTPException(status_code=404, detail="Vokabular nicht gefunden")
    errors = await validate_metadata(
        db, "vocabulary_term", data.metadata_, str(vocab_id)
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    term = VocabularyTerm(**data.model_dump(exclude={"vocabulary_id"}) | {"vocabulary_id": vocab_id})
    db.add(term)
    await db.flush()
    return term


@router.put(
    "/terms/{term_id}",
    response_model=VocabularyTermRead,
    dependencies=[require_role("admin")],
    summary="Update a vocabulary term",
    responses={
        404: {"description": "Term not found"},
        422: {"description": "Metadata validation failed"},
        403: {"description": "Insufficient permissions"},
    },
)
async def update_term(
    term_id: uuid.UUID, data: VocabularyTermCreate, db: DBDep
) -> VocabularyTerm:
    result = await db.execute(select(VocabularyTerm).where(VocabularyTerm.id == term_id))
    term = result.scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="Term nicht gefunden")
    errors = await validate_metadata(
        db, "vocabulary_term", data.metadata_, str(term.vocabulary_id)
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    for k, v in data.model_dump(exclude={"vocabulary_id"}).items():
        setattr(term, k, v)
    return term


@router.delete(
    "/terms/{term_id}",
    status_code=204,
    dependencies=[require_role("admin")],
    summary="Delete a vocabulary term",
    responses={
        404: {"description": "Term not found"},
        403: {"description": "Insufficient permissions"},
    },
)
async def delete_term(term_id: uuid.UUID, db: DBDep) -> None:
    result = await db.execute(select(VocabularyTerm).where(VocabularyTerm.id == term_id))
    term = result.scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="Term nicht gefunden")
    await db.delete(term)


@router.post(
    "/{vocab_id}/import",
    dependencies=[require_role("admin")],
    summary="Import vocabulary terms from CSV/TSV or JSON with optional dry-run",
    responses={
        404: {"description": "Vocabulary not found"},
        422: {"description": "Import mapping, parsing, or file type error"},
        403: {"description": "Insufficient permissions"},
    },
)
async def import_terms(
    vocab_id: uuid.UUID,
    file: UploadFile,
    db: DBDep,
    _: CurrentUser,
    strategy: Literal["append", "replace"] = Query("append"),
    dry_run: bool = Query(True),
    mapping: str | None = Form(None),
) -> dict:
    """Import vocabulary terms from CSV or JSON with optional dry-run."""
    vocab_result = await db.execute(select(Vocabulary).where(Vocabulary.id == vocab_id))
    if vocab_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Vokabular nicht gefunden")

    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".csv") or filename.endswith(".tsv"):
        try:
            parsed_mapping = vocabulary_import_service.parse_mapping(mapping)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not parsed_mapping:
            raise HTTPException(status_code=422, detail="CSV-Import benötigt ein Mapping")
        try:
            terms, errors = vocabulary_import_service.parse_csv_terms(content, parsed_mapping)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"CSV konnte nicht verarbeitet werden: {exc}") from exc
    elif filename.endswith(".json"):
        try:
            terms, errors = vocabulary_import_service.parse_json_terms(content)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"JSON konnte nicht verarbeitet werden: {exc}") from exc
    else:
        raise HTTPException(status_code=422, detail="Nur CSV/TSV oder JSON werden unterstützt")

    if errors:
        return {
            "strategy": strategy,
            "dry_run": dry_run,
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "errors": errors,
        }

    result = await vocabulary_import_service.import_vocabulary_terms(
        db=db,
        vocab_id=vocab_id,
        terms=terms,
        strategy=strategy,
        dry_run=dry_run,
    )
    result["strategy"] = strategy
    result["dry_run"] = dry_run
    return result
