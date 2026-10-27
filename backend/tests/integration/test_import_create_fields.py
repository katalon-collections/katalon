# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_ensure_field_vocabulary_binds_and_reuses(async_client) -> None:
    import katalon.database as database_module
    from katalon.core.models import FieldDefinition, Vocabulary
    from katalon.services.vocabulary_reference_service import ensure_field_vocabulary

    name = f"Genre-{uuid.uuid4().hex[:8]}"
    async with database_module.AsyncSessionLocal() as session:
        first = FieldDefinition(target_type="occurrence", name="a", field_type="vocab", label={}, settings={})
        second = FieldDefinition(target_type="occurrence", name="b", field_type="vocab", label={}, settings={})
        text = FieldDefinition(target_type="occurrence", name="c", field_type="text", label={}, settings={})
        for field in (first, second, text):
            await ensure_field_vocabulary(session, field, name)
        count = len((await session.execute(select(Vocabulary).where(Vocabulary.name == name))).scalars().all())
        assert count == 1
        assert first.settings["vocabulary_id"] == second.settings["vocabulary_id"]
        assert "vocabulary_id" not in text.settings
        await session.rollback()
