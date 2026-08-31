import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.services.schema_service import prepare_metadata, validate_metadata


def make_field(
    name: str,
    *,
    is_required: bool = False,
    is_repeatable: bool = False,
    field_type: str = "text",
    is_translatable: bool = False,
) -> MagicMock:
    f = MagicMock()
    f.name = name
    f.is_required = is_required
    f.is_repeatable = is_repeatable
    f.field_type = field_type
    f.is_translatable = is_translatable
    f.settings = {}
    f.id = uuid.uuid4()
    return f


def make_group_field(name: str, sub_fields: list[MagicMock], *, is_required: bool = False) -> MagicMock:
    f = make_field(name, is_required=is_required, field_type="group")
    f.is_repeatable = True
    return f, sub_fields


def mock_db(*top_fields: MagicMock, sub_fields: list[MagicMock] | None = None) -> AsyncMock:
    """Mock DB that returns top_fields for the first execute call and sub_fields for subsequent calls."""
    top_result = MagicMock()
    top_result.scalars.return_value.all.return_value = list(top_fields)

    sub_result = MagicMock()
    sub_result.scalars.return_value.all.return_value = list(sub_fields or [])

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[top_result, sub_result] + [sub_result] * 10)
    return db


@pytest.mark.asyncio
async def test_no_fields_no_errors() -> None:
    db = mock_db()
    errors = await validate_metadata(db, "object", {})
    assert errors == []


@pytest.mark.asyncio
async def test_required_field_missing() -> None:
    db = mock_db(make_field("title", is_required=True))
    errors = await validate_metadata(db, "object", {})
    assert len(errors) == 1
    assert "title" in errors[0]


@pytest.mark.asyncio
async def test_required_field_empty_string() -> None:
    db = mock_db(make_field("title", is_required=True))
    errors = await validate_metadata(db, "object", {"title": ""})
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_required_field_empty_list() -> None:
    db = mock_db(make_field("tags", is_required=True, is_repeatable=True))
    errors = await validate_metadata(db, "object", {"tags": []})
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_required_field_present_no_error() -> None:
    db = mock_db(make_field("title", is_required=True))
    errors = await validate_metadata(db, "object", {"title": "Bahnhofstraße"})
    assert errors == []


@pytest.mark.asyncio
async def test_repeatable_not_list_is_error() -> None:
    db = mock_db(make_field("tags", is_repeatable=True))
    errors = await validate_metadata(db, "object", {"tags": "einzelner-wert"})
    assert len(errors) == 1
    assert "Liste" in errors[0]


@pytest.mark.asyncio
async def test_repeatable_list_ok() -> None:
    db = mock_db(make_field("tags", is_repeatable=True))
    errors = await validate_metadata(db, "object", {"tags": ["a", "b"]})
    assert errors == []


@pytest.mark.asyncio
async def test_non_repeatable_list_is_error() -> None:
    db = mock_db(make_field("title", is_repeatable=False))
    errors = await validate_metadata(db, "object", {"title": ["a", "b"]})
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_optional_field_absent_no_error() -> None:
    db = mock_db(make_field("description", is_required=False))
    errors = await validate_metadata(db, "object", {})
    assert errors == []


@pytest.mark.asyncio
async def test_date_field_requires_a_real_calendar_date() -> None:
    field = make_field("birth_date", field_type="date")

    assert await validate_metadata(mock_db(field), "entity", {"birth_date": "1987-08-10"}) == []
    assert await validate_metadata(mock_db(field), "entity", {"birth_date": "1987-08-46"})
    assert await validate_metadata(mock_db(field), "entity", {"birth_date": "1987-13"})


@pytest.mark.asyncio
async def test_date_field_accepts_bce_years() -> None:
    """BCE years use signed ISO with zero-padded year; ISO year -0043 = 44 v. Chr. (year-0 offset)."""
    field = make_field("birth_date", field_type="date")

    valid = [
        "-0043",               # 44 v. Chr., Jahr allein
        "-0043-06",            # 44 v. Chr., Jahr+Monat
        "-0043-06-15",         # 44 v. Chr., exaktes Datum
        "-0001-12-31",         # 2 v. Chr.
        "0000",                # 1 v. Chr. (Jahr 0)
        "0000-02-29",          # Jahr 0 ist ein Schaltjahr
        "-0004-02-29",         # -4 ist durch 4 teilbar → Schaltjahr
        "-4000-01-01",
    ]
    for v in valid:
        assert await validate_metadata(mock_db(field), "entity", {"birth_date": v}) == [], v

    invalid = [
        "-43",                 # Jahr muss 4-stellig sein
        "--0043",
        "-0043-13",            # Monat 13
        "-0043-06-31",         # Juni hat 30 Tage
        "-0043-02-29",         # 44 v. Chr. (-43) ist kein Schaltjahr
        "-0043-06-00",         # Tag 0
    ]
    for v in invalid:
        assert await validate_metadata(mock_db(field), "entity", {"birth_date": v}), v


@pytest.mark.asyncio
async def test_date_field_accepts_ranges_and_uncertainty() -> None:
    """EDTF-lite: '~' = circa, '?' = unsicher, 'START/END' = Zeitraum (Seiten optional offen)."""
    field = make_field("birth_date", field_type="date")

    valid = [
        "1900~",        # circa
        "1900?",        # unsicher
        "1900~?",       # beides
        "1900/1950",    # Zeitraum
        "1900/",        # offenes Ende (nach 1900)
        "/1950",        # offener Anfang (vor 1950)
        "1900~/1950?",  # Zeitraum mit Qualifiern je Seite
    ]
    for v in valid:
        assert await validate_metadata(mock_db(field), "entity", {"birth_date": v}) == [], v

    invalid = [
        "1900!",
        "/",
        "1900/1950/2000",
        "1900-13~",
    ]
    for v in invalid:
        assert await validate_metadata(mock_db(field), "entity", {"birth_date": v}), v


@pytest.mark.asyncio
async def test_multiple_fields_multiple_errors() -> None:
    db = mock_db(
        make_field("title", is_required=True),
        make_field("rights", is_required=True),
    )
    errors = await validate_metadata(db, "object", {})
    assert len(errors) == 2


@pytest.mark.asyncio
async def test_valid_complex_metadata() -> None:
    db = mock_db(
        make_field("title", is_required=True),
        make_field("tags", is_repeatable=True),
        make_field("description"),
    )
    errors = await validate_metadata(db, "object", {
        "title": "Bahnhofstraße bei Nacht",
        "tags": ["zürich", "nacht", "strasse"],
    })
    assert errors == []


@pytest.mark.asyncio
async def test_translatable_field_accepts_lang_dict() -> None:
    db = mock_db(make_field("description", is_translatable=True))
    errors = await validate_metadata(db, "object", {"description": {"de": "Hallo", "en": "Hello"}})
    assert errors == []


@pytest.mark.asyncio
async def test_translatable_field_rejects_plain_string() -> None:
    db = mock_db(make_field("description", is_translatable=True))
    errors = await validate_metadata(db, "object", {"description": "Hallo"})
    assert len(errors) == 1
    assert "Übersetzbarer Wert" in errors[0]


@pytest.mark.asyncio
async def test_translatable_field_rejects_non_string_value() -> None:
    db = mock_db(make_field("description", is_translatable=True))
    errors = await validate_metadata(db, "object", {"description": {"de": 123}})
    assert len(errors) == 1



# ---------------------------------------------------------------------------
# Group / container field tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_field_not_a_list_is_error() -> None:
    group = make_field("foerderung", field_type="group")
    db = mock_db(group, sub_fields=[])
    errors = await validate_metadata(db, "object", {"foerderung": "not-a-list"})
    assert len(errors) == 1
    assert "Liste" in errors[0]


@pytest.mark.asyncio
async def test_group_field_required_empty_list() -> None:
    group = make_field("foerderung", field_type="group", is_required=True)
    db = mock_db(group, sub_fields=[])
    errors = await validate_metadata(db, "object", {"foerderung": []})
    assert len(errors) == 1
    assert "foerderung" in errors[0]


@pytest.mark.asyncio
async def test_group_field_required_sub_field_missing() -> None:
    group = make_field("foerderung", field_type="group")
    nummer = make_field("nummer", is_required=True)
    db = mock_db(group, sub_fields=[nummer])
    errors = await validate_metadata(db, "object", {"foerderung": [{"nummer": ""}]})
    assert len(errors) == 1
    assert "foerderung.nummer" in errors[0]
    assert "Eintrag 1" in errors[0]


@pytest.mark.asyncio
async def test_group_field_valid_instances() -> None:
    group = make_field("foerderung", field_type="group")
    nummer = make_field("nummer", is_required=True)
    db = mock_db(group, sub_fields=[nummer])
    errors = await validate_metadata(db, "object", {
        "foerderung": [
            {"nummer": "FU-2023-001"},
            {"nummer": "FU-2024-042"},
        ]
    })
    assert errors == []


@pytest.mark.asyncio
async def test_group_field_sub_field_regex_violation() -> None:
    group = make_field("foerderung", field_type="group")
    url = make_field("url")
    url.settings = {"validation_regex": r"^https?://.+"}
    db = mock_db(group, sub_fields=[url])
    errors = await validate_metadata(db, "object", {"foerderung": [{"url": "not-a-url"}]})
    assert len(errors) == 1
    assert "foerderung.url" in errors[0]


@pytest.mark.asyncio
async def test_group_field_optional_absent() -> None:
    group = make_field("foerderung", field_type="group")
    db = mock_db(group, sub_fields=[])
    errors = await validate_metadata(db, "object", {})
    assert errors == []


@pytest.mark.asyncio
async def test_group_relation_sub_field_validates_structure() -> None:
    group = make_field("object_history", field_type="group")
    person = make_field("person", field_type="relation")
    person.settings = {"target_type": "entity"}
    db = mock_db(group, sub_fields=[person])
    errors = await validate_metadata(
        db, "object", {"object_history": [{"person": {"label": "No ID"}}]}
    )
    assert len(errors) == 1
    assert "object_history.person" in errors[0]


@pytest.mark.asyncio
async def test_group_authority_sub_field_validates_structure_and_source() -> None:
    group = make_field("materials", field_type="group")
    material = make_field("material", field_type="authority")
    material.settings = {"source": "gnd"}
    db = mock_db(group, sub_fields=[material])
    errors = await validate_metadata(
        db,
        "object",
        {"materials": [{"material": {"source": "viaf", "external_id": "123", "label": "Holz"}}]},
    )
    assert len(errors) == 1
    assert "materials.material" in errors[0]
    assert "Authority-Quelle" in errors[0]

    valid_errors = await validate_metadata(
        mock_db(group, sub_fields=[material]),
        "object",
        {"materials": [{"material": {"source": "gnd", "external_id": "123", "label": "Holz"}}]},
    )
    assert valid_errors == []


@pytest.mark.asyncio
async def test_top_level_authority_field_validates_structure() -> None:
    authority = make_field("creator", field_type="authority")
    authority.settings = {"source": "gnd"}
    errors = await validate_metadata(
        mock_db(authority),
        "object",
        {"creator": {"source": "gnd", "external_id": "123", "label": ""}},
    )
    assert len(errors) == 1
    assert "source, external_id und label" in errors[0]


@pytest.mark.asyncio
async def test_prepare_metadata_applies_default() -> None:
    language = make_field("language")
    language.settings = {"default_value": "de"}
    metadata = await prepare_metadata(mock_db(language), "object", {})
    assert metadata == {"language": "de"}


@pytest.mark.asyncio
async def test_prepare_metadata_preserves_locked_value_for_editor() -> None:
    institution = make_field("institution")
    institution.settings = {"is_locked": True}
    metadata = await prepare_metadata(
        mock_db(institution),
        "object",
        {"institution": "changed"},
        existing={"institution": "original"},
    )
    assert metadata == {"institution": "original"}


@pytest.mark.asyncio
async def test_prepare_metadata_allows_admin_to_change_locked_value() -> None:
    institution = make_field("institution")
    institution.settings = {"is_locked": True}
    metadata = await prepare_metadata(
        mock_db(institution),
        "object",
        {"institution": "changed"},
        existing={"institution": "original"},
        can_edit_locked=True,
    )
    assert metadata == {"institution": "changed"}


# ---------------------------------------------------------------------------
# URL field type
# ---------------------------------------------------------------------------

def make_url_field(name: str = "link", *, is_repeatable: bool = False) -> MagicMock:
    return make_field(name, is_repeatable=is_repeatable, field_type="url")


@pytest.mark.asyncio
async def test_url_value_valid() -> None:
    db = mock_db(make_url_field())
    errors = await validate_metadata(
        db, "object", {"link": {"value": "https://example.org", "label": "Beispiel"}}
    )
    assert errors == []


@pytest.mark.asyncio
async def test_url_value_without_label_valid() -> None:
    db = mock_db(make_url_field())
    errors = await validate_metadata(db, "object", {"link": {"value": "https://example.org"}})
    assert errors == []


@pytest.mark.asyncio
async def test_url_value_rejects_non_http() -> None:
    db = mock_db(make_url_field())
    errors = await validate_metadata(db, "object", {"link": {"value": "ftp://example.org"}})
    assert errors == ["Feld 'link': URL-Wert (value) muss eine vollständige http(s)-URL sein."]


@pytest.mark.asyncio
async def test_url_value_rejects_relative() -> None:
    db = mock_db(make_url_field())
    errors = await validate_metadata(db, "object", {"link": {"value": "/objects/1"}})
    assert errors == ["Feld 'link': URL-Wert (value) muss eine vollständige http(s)-URL sein."]


@pytest.mark.asyncio
async def test_url_value_rejects_plain_string() -> None:
    db = mock_db(make_url_field())
    errors = await validate_metadata(db, "object", {"link": "https://example.org"})
    assert errors == ["Feld 'link': URL muss ein Objekt {value, label} sein."]


@pytest.mark.asyncio
async def test_url_repeatable_list_valid() -> None:
    db = mock_db(make_url_field("links", is_repeatable=True))
    errors = await validate_metadata(
        db,
        "object",
        {"links": [{"value": "https://a.example"}, {"value": "https://b.example", "label": "B"}]},
    )
    assert errors == []


@pytest.mark.asyncio
async def test_url_repeatable_requires_list() -> None:
    db = mock_db(make_url_field("links", is_repeatable=True))
    errors = await validate_metadata(db, "object", {"links": {"value": "https://a.example"}})
    assert errors == ["Feld 'links' muss eine Liste sein (wiederholbar)."]


# ---------------------------------------------------------------------------
# PID fields are system-managed
# ---------------------------------------------------------------------------

def make_pid_field(name: str = "pid", *, is_repeatable: bool = False) -> MagicMock:
    return make_field(name, is_repeatable=is_repeatable, field_type="pid")


@pytest.mark.asyncio
async def test_prepare_metadata_drops_manual_pid_input_on_create() -> None:
    pid = make_pid_field()
    metadata = await prepare_metadata(mock_db(pid), "object", {"pid": {"value": "urn:x", "label": "x"}})
    assert "pid" not in metadata


@pytest.mark.asyncio
async def test_prepare_metadata_preserves_stored_pid_on_update() -> None:
    pid = make_pid_field()
    stored = {"value": "ark:/99999/abc", "label": "ARK"}
    metadata = await prepare_metadata(
        mock_db(pid), "object", {"pid": {"value": "tampered", "label": "x"}}, existing={"pid": stored}
    )
    assert metadata["pid"] == stored


@pytest.mark.asyncio
async def test_prepare_metadata_pid_protection_not_bypassable_by_admin() -> None:
    pid = make_pid_field()
    stored = {"value": "urn:nbn:de:x", "label": "URN"}
    metadata = await prepare_metadata(
        mock_db(pid), "object", {"pid": None}, existing={"pid": stored}, can_edit_locked=True
    )
    assert metadata["pid"] == stored


@pytest.mark.asyncio
async def test_prepare_metadata_keeps_repeatable_pid_entries() -> None:
    pid = make_pid_field("pids", is_repeatable=True)
    stored = [{"value": "urn:nbn:de:x", "label": "URN"}]
    metadata = await prepare_metadata(
        mock_db(pid), "object", {"pids": []}, existing={"pids": stored}
    )
    assert metadata["pids"] == stored


def test_protect_pid_fields_standalone() -> None:
    from katalon.services.schema_service import protect_pid_fields

    pid = make_pid_field()
    text = make_field("title")
    fields = [text, pid]
    existing = {"pid": {"value": "urn:nbn:de:1", "label": "URN"}}
    protected = protect_pid_fields(fields, {"title": "T", "pid": {"value": "hack"}}, existing)
    assert protected == {"title": "T", "pid": {"value": "urn:nbn:de:1", "label": "URN"}}

    fresh = protect_pid_fields(fields, {"title": "T", "pid": {"value": "hack"}}, None)
    assert fresh == {"title": "T"}
