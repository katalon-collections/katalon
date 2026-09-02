# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

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


async def validate_relation_type_applicability(
    db: AsyncSession, from_type: str, to_type: str, relation_type: str
) -> str | None:
    """Return an error message if the relation type is not allowed for this type pair.

    Terms missing from relation vocabularies and terms without
    applies_from/applies_to constraints stay unrestricted.
    """
    result = await db.execute(
        select(VocabularyTerm)
        .join(Vocabulary, Vocabulary.id == VocabularyTerm.vocabulary_id)
        .where(Vocabulary.kind == "relation", VocabularyTerm.term == relation_type)
    )
    terms = list(result.scalars().all())
    if not terms:
        return None
    for term in terms:
        if term.applies_from and from_type not in term.applies_from:
            continue
        if term.applies_to and to_type not in term.applies_to:
            continue
        return None
    return f"Relationstyp '{relation_type}' ist für {from_type} → {to_type} nicht erlaubt."
