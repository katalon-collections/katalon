import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import Vocabulary, VocabularyTerm
from katalon.core.schemas import (
    VocabularyCreate, VocabularyRead,
    VocabularyTermCreate, VocabularyTermRead,
)

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

@router.get("", response_model=list[VocabularyRead])
async def list_vocabularies(db: DBDep) -> list[Vocabulary]:
    result = await db.execute(select(Vocabulary).order_by(Vocabulary.name))
    return list(result.scalars().all())


@router.post("", response_model=VocabularyRead, status_code=201)
async def create_vocabulary(data: VocabularyCreate, db: DBDep, _: CurrentUser) -> Vocabulary:
    vocab = Vocabulary(**data.model_dump())
    db.add(vocab)
    await db.commit()
    return vocab


# ---------------------------------------------------------------------------
# Terms – flat list
# ---------------------------------------------------------------------------

@router.get("/{vocab_id}/terms", response_model=list[VocabularyTermRead])
async def list_terms(vocab_id: uuid.UUID, db: DBDep) -> list[VocabularyTerm]:
    result = await db.execute(
        select(VocabularyTerm)
        .where(VocabularyTerm.vocabulary_id == vocab_id)
        .order_by(VocabularyTerm.term)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Terms – tree
# ---------------------------------------------------------------------------

@router.get("/{vocab_id}/tree", response_model=list[VocabularyTermNode])
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


@router.get("/{vocab_id}/terms/{term_id}/ancestors", response_model=list[VocabularyTermRead])
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

@router.post("/{vocab_id}/terms", response_model=VocabularyTermRead, status_code=201)
async def create_term(
    vocab_id: uuid.UUID, data: VocabularyTermCreate, db: DBDep, _: CurrentUser
) -> VocabularyTerm:
    term = VocabularyTerm(**data.model_dump() | {"vocabulary_id": vocab_id})
    db.add(term)
    await db.flush()
    return term


@router.put("/terms/{term_id}", response_model=VocabularyTermRead)
async def update_term(
    term_id: uuid.UUID, data: VocabularyTermCreate, db: DBDep, _: CurrentUser
) -> VocabularyTerm:
    result = await db.execute(select(VocabularyTerm).where(VocabularyTerm.id == term_id))
    term = result.scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="Term nicht gefunden")
    for k, v in data.model_dump().items():
        setattr(term, k, v)
    return term


@router.delete("/terms/{term_id}", status_code=204)
async def delete_term(term_id: uuid.UUID, db: DBDep, _: CurrentUser) -> None:
    result = await db.execute(select(VocabularyTerm).where(VocabularyTerm.id == term_id))
    term = result.scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="Term nicht gefunden")
    await db.delete(term)
