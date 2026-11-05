# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from katalon.core.models import Entity, Vocabulary, VocabularyTerm


def _vocab_field(vocab_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        name="plattform",
        field_type="vocab",
        parent_id=None,
        is_repeatable=False,
        label={"de": "Plattform"},
        settings={"vocabulary_id": str(vocab_id)},
    )


def _relation_field(
    name: str, *, repeatable: bool = False, fixed: str | None = "rel-0001"
) -> SimpleNamespace:
    settings: dict[str, str] = {"target_type": "entity"}
    if fixed:
        settings["fixed_relation_type"] = fixed
    return SimpleNamespace(
        name=name,
        field_type="relation",
        parent_id=None,
        is_repeatable=repeatable,
        label={"de": "Entwickler"},
        settings=settings,
    )


@pytest.mark.asyncio
async def test_vocab_matches_label_in_any_language_without_duplicate(app) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.services.import_resolution import resolve_vocab_terms

    async with AsyncSessionLocal() as session:
        vocab = Vocabulary(name=f"Plattformen-{uuid.uuid4().hex}")
        session.add(vocab)
        await session.flush()
        curated = VocabularyTerm(
            vocabulary_id=vocab.id, term="system-162", label={"de": "Windows 2000", "en": "Win 2000"}
        )
        session.add(curated)
        await session.flush()

        records = [{"plattform": "windows  2000"}, {"plattform": "Win 2000"}, {"plattform": "Neu"}]
        report = await resolve_vocab_terms(session, {"plattform": _vocab_field(vocab.id)}, records)

        assert records[0]["plattform"] == {"id": str(curated.id), "label": "Windows 2000"}
        assert records[1]["plattform"] == {"id": str(curated.id), "label": "Windows 2000"}
        assert report.new_terms == {"plattform": {"Neu"}}
        count = await session.scalar(
            select(func.count()).select_from(VocabularyTerm).where(
                VocabularyTerm.vocabulary_id == vocab.id
            )
        )
        assert count == 2
        await session.rollback()


@pytest.mark.asyncio
async def test_vocab_match_only_drops_unknown_and_label_clash_is_ambiguous(app) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.services.import_resolution import resolve_vocab_terms

    async with AsyncSessionLocal() as session:
        vocab = Vocabulary(name=f"Plattformen-{uuid.uuid4().hex}")
        session.add(vocab)
        await session.flush()
        session.add(VocabularyTerm(vocabulary_id=vocab.id, term="a", label={"de": "Doppelt"}))
        session.add(VocabularyTerm(vocabulary_id=vocab.id, term="b", label={"en": "Doppelt"}))
        await session.flush()

        records = [{"plattform": "Unbekannt"}, {"plattform": "Doppelt"}]
        report = await resolve_vocab_terms(
            session, {"plattform": _vocab_field(vocab.id)}, records, {"plattform": "match_only"}
        )

        assert "plattform" not in records[0]
        assert report.unmatched == {"plattform": {"unbekannt"}}
        assert 1 in report.row_errors and "mehrdeutig" in report.row_errors[1][0]
        assert report.new_terms == {}
        await session.rollback()


@pytest.mark.asyncio
async def test_relation_lookup_by_idno_and_missing_target_is_row_error(app) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.services.import_resolution import resolve_relations

    idno = f"ENT-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as session:
        target = Entity(idno=idno, metadata_={"name": "Radon Labs GmbH"}, status="draft")
        session.add(target)
        await session.flush()

        records = [{"entwickler": idno}, {"entwickler": "fehlt-1"}]
        report = await resolve_relations(session, {"entwickler": _relation_field("entwickler")}, records)

        assert records[0]["entwickler"] == {
            "id": str(target.id), "label": "Radon Labs GmbH", "relation_type": "rel-0001"
        }
        assert "entwickler" not in records[1]
        assert "nicht gefunden" in report.row_errors[1][0]
        assert report.created_records == []
        await session.rollback()


@pytest.mark.asyncio
async def test_relation_lookup_by_label_ambiguous_and_repeatable(app) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.services.import_resolution import resolve_relations

    suffix = uuid.uuid4().hex
    async with AsyncSessionLocal() as session:
        first = Entity(metadata_={"name": f"Studio {suffix}"}, status="draft")
        twin_a = Entity(metadata_={"name": f"Zwilling {suffix}"}, status="draft")
        twin_b = Entity(metadata_={"name": f"Zwilling {suffix}"}, status="draft")
        session.add_all([first, twin_a, twin_b])
        await session.flush()

        records = [{"entwickler": [f"studio {suffix}"]}, {"entwickler": f"Zwilling {suffix}"}]
        report = await resolve_relations(
            session,
            {"entwickler": _relation_field("entwickler", repeatable=True)},
            records,
            {"entwickler": {"lookup": "label"}},
        )

        assert records[0]["entwickler"] == [
            {"id": str(first.id), "label": f"Studio {suffix}", "relation_type": "rel-0001"}
        ]
        assert "mehrdeutig" in report.row_errors[1][0]
        await session.rollback()


@pytest.mark.asyncio
async def test_relation_on_missing_create_makes_one_draft_and_reuses_it(app) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.services.import_resolution import resolve_relations

    name = f"Sproing {uuid.uuid4().hex}"
    async with AsyncSessionLocal() as session:
        records = [{"entwickler": name}, {"entwickler": name}]
        report = await resolve_relations(
            session,
            {"entwickler": _relation_field("entwickler")},
            records,
            {"entwickler": {"lookup": "label", "on_missing": "create"}},
        )

        assert report.row_errors == {}
        assert len(report.created_records) == 1
        target_type, created = report.created_records[0]
        assert target_type == "entity" and created.status == "draft"
        assert created.metadata_ == {"label": name}
        assert records[0]["entwickler"]["id"] == records[1]["entwickler"]["id"] == str(created.id)
        await session.rollback()


@pytest.mark.asyncio
async def test_relation_without_fixed_type_is_refused(app) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.services.import_resolution import resolve_relations

    async with AsyncSessionLocal() as session:
        records = [{"entwickler": "x"}]
        report = await resolve_relations(
            session, {"entwickler": _relation_field("entwickler", fixed=None)}, records
        )
        assert "kein fester Relationstyp" in report.row_errors[0][0]
        assert "entwickler" not in records[0]
        await session.rollback()


@pytest.mark.asyncio
async def test_worker_import_links_relation_and_dry_run_creates_nothing(
    app, async_client, auth_headers, monkeypatch
) -> None:
    import asyncio

    import katalon.database as database_module
    from katalon.api.v1 import importer
    from katalon.core.models import FieldDefinition, Occurrence, Relation, User
    from katalon.workers.import_tasks import import_records_task

    class _FakeRedis:
        def get(self, key: str) -> None:
            return None

    monkeypatch.setattr("redis.from_url", lambda *a, **kw: _FakeRedis())
    monkeypatch.setattr(import_records_task, "update_state", lambda **kw: None)
    suffix = uuid.uuid4().hex[:8]
    field = f"entwickler_{suffix}"
    known = f"Bekannt {suffix}"
    unknown = f"Neu {suffix}"
    async with database_module.AsyncSessionLocal() as session:
        target = Entity(metadata_={"name": known}, status="draft")
        session.add(target)
        session.add(
            FieldDefinition(
                target_type="occurrence", name=field, field_type="relation", label={"de": "Entwickler"},
                settings={"target_type": "entity", "fixed_relation_type": "rel-0001"},
            )
        )
        user = await session.scalar(select(User).where(User.email == "admin@katalon.dev"))
        user_id = str(user.id)
        target_id = target.id
        await session.commit()

    rows = [{"Label": f"a{suffix}", "Dev": known}, {"Label": f"b{suffix}", "Dev": unknown}]
    options = {field: {"lookup": "label", "on_missing": "error"}}
    monkeypatch.setattr(importer, "_load_rows", lambda upload_id: rows)
    body = {
        "upload_id": "x",
        "record_type": "occurrence",
        "mapping": {"Label": {"target": "label"}, "Dev": {"target": field}},
        "relation_options": options,
    }
    dry = await async_client.post("/v1/importer/dry-run", headers=auth_headers, json=body)
    assert dry.status_code == 200, dry.text
    messages = [e["message"] for e in dry.json()["errors"]]
    assert any(unknown in m and "nicht gefunden" in m for m in messages)
    assert not any(known in m for m in messages)

    body["relation_options"] = {field: {"lookup": "label", "on_missing": "create"}}
    dry = await async_client.post("/v1/importer/dry-run", headers=auth_headers, json=body)
    assert dry.json()["errors"] == []
    assert any("würden als Entwurf angelegt" in w["message"] for w in dry.json()["warnings"])
    async with database_module.AsyncSessionLocal() as session:
        assert await session.scalar(
            select(func.count()).select_from(Entity).where(Entity.metadata_["label"].astext == unknown)
        ) == 0

    result = await asyncio.to_thread(
        import_records_task.run,
        "occurrence",
        rows,
        {"Label": "label", "Dev": field},
        user_id=user_id,
        relation_options={field: {"lookup": "label", "on_missing": "error"}},
    )
    assert result["created"] == 1
    assert any(unknown in e["error"] for e in result["errors"])
    async with database_module.AsyncSessionLocal() as session:
        occ = await session.scalar(
            select(Occurrence).where(Occurrence.metadata_["label"].astext == f"a{suffix}")
        )
        assert occ is not None
        assert occ.metadata_[field]["id"] == str(target_id)
        rel = await session.scalar(select(Relation).where(Relation.from_id == occ.id))
        assert rel is not None and rel.to_id == target_id and rel.relation_type == "rel-0001"
