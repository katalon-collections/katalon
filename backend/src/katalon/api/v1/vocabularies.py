import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import Vocabulary, VocabularyTerm
from katalon.core.schemas import (
    VocabularyCreate, VocabularyRead,
    VocabularyTermCreate, VocabularyTermRead,
)

router = APIRouter(prefix="/vocabularies", tags=["vocabularies"])


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


@router.get("/{vocab_id}/terms", response_model=list[VocabularyTermRead])
async def list_terms(vocab_id: uuid.UUID, db: DBDep) -> list[VocabularyTerm]:
    result = await db.execute(
        select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab_id)
    )
    return list(result.scalars().all())


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
