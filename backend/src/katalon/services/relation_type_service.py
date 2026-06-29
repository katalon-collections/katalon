from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import Relation, Vocabulary, VocabularyTerm


async def sync_relation_type_terms(db: AsyncSession, vocab: Vocabulary) -> None:
    result = await db.execute(
        select(VocabularyTerm.term).where(VocabularyTerm.vocabulary_id == vocab.id)
    )
    existing_terms = {term for term in result.scalars().all() if term}

    result = await db.execute(
        select(Relation.relation_type).distinct().order_by(Relation.relation_type)
    )
    relation_terms = {term for term in result.scalars().all() if term}

    for term_key in sorted(relation_terms - existing_terms):
        db.add(
            VocabularyTerm(
                vocabulary_id=vocab.id,
                term=term_key,
                label={"de": term_key, "en": term_key},
                inverse_label={},
            )
        )
