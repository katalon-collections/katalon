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


@pytest.mark.asyncio
async def test_import_assigns_selected_subtype_to_new_fields(app, auth_headers, monkeypatch) -> None:
    import asyncio

    import katalon.database as database_module
    from katalon.core.models import FieldDefinition, RecordSubtype, User
    from katalon.workers.import_tasks import import_records_task

    class _FakeRedis:
        def get(self, key: str) -> None:
            return None

    monkeypatch.setattr("redis.from_url", lambda *a, **kw: _FakeRedis())
    monkeypatch.setattr(import_records_task, "update_state", lambda **kw: None)

    suffix = uuid.uuid4().hex[:8]
    subtype, field = f"werk_{suffix}", f"feld_{suffix}"
    async with database_module.AsyncSessionLocal() as session:
        session.add(RecordSubtype(primary_type="occurrence", name=subtype, label={"de": "Werk"}))
        user = await session.scalar(select(User).where(User.email == "admin@katalon.dev"))
        user_id = str(user.id)
        await session.commit()

    await asyncio.to_thread(
        import_records_task.run,
        "occurrence",
        [{"Label": "x", "Neu": "y"}],
        {"Label": "label", "Neu": field},
        user_id=user_id,
        subtype=subtype,
        fields_to_create=[{"name": field, "field_type": "text", "label_de": "Neu"}],
    )

    async with database_module.AsyncSessionLocal() as session:
        fd = await session.scalar(
            select(FieldDefinition).where(
                FieldDefinition.target_type == "occurrence", FieldDefinition.name == field
            )
        )
        assert fd is not None
        assert fd.target_subtype == subtype


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["extend", "match_only"])
async def test_import_vocab_mode_matches_normalized_and_dedupes(app, monkeypatch, mode) -> None:
    import asyncio

    import katalon.database as database_module
    from katalon.core.models import FieldDefinition, User, Vocabulary, VocabularyTerm
    from katalon.workers.import_tasks import import_records_task

    class _FakeRedis:
        def get(self, key: str) -> None:
            return None

    monkeypatch.setattr("redis.from_url", lambda *a, **kw: _FakeRedis())
    monkeypatch.setattr(import_records_task, "update_state", lambda **kw: None)

    suffix = uuid.uuid4().hex[:8]
    field = f"ort_{suffix}"
    async with database_module.AsyncSessionLocal() as session:
        vocab = Vocabulary(name=f"Orte-{suffix}")
        session.add(vocab)
        await session.flush()
        session.add(VocabularyTerm(vocabulary_id=vocab.id, term="Berlin", label={"de": "Berlin"}))
        session.add(
            FieldDefinition(
                target_type="occurrence", name=field, field_type="vocab", label={"de": "Ort"},
                settings={"vocabulary_id": str(vocab.id)},
            )
        )
        user = await session.scalar(select(User).where(User.email == "admin@katalon.dev"))
        user_id = str(user.id)
        vocab_id = vocab.id
        await session.commit()

    rows = [
        {"Label": f"a{suffix}", "Ort": "berlin"},
        {"Label": f"b{suffix}", "Ort": "  BERLIN "},
        {"Label": f"c{suffix}", "Ort": "Köln"},
        {"Label": f"d{suffix}", "Ort": "köln"},
    ]
    result = await asyncio.to_thread(
        import_records_task.run,
        "occurrence",
        rows,
        {"Label": "label", "Ort": field},
        user_id=user_id,
        vocab_modes={field: mode},
    )

    async with database_module.AsyncSessionLocal() as session:
        terms = (
            await session.scalars(select(VocabularyTerm.term).where(VocabularyTerm.vocabulary_id == vocab_id))
        ).all()
    if mode == "extend":
        assert sorted(terms) == ["Berlin", "Köln"]
    else:
        assert terms == ["Berlin"]
        assert any("Köln" in w["warning"] for w in result["warnings"])
