# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Unit tests for idno_service – pure logic, no DB required."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.services.idno_service import (
    format_idno,
    maybe_advance_counter,
    peek_next_idno,
    validate_idno_pattern,
)

# ---------------------------------------------------------------------------
# format_idno
# ---------------------------------------------------------------------------

def test_format_idno_plain_counter():
    assert format_idno("obj_{counter}", 1, "object") == "obj_1"
    assert format_idno("obj_{counter}", 42, "object") == "obj_42"


def test_format_idno_zero_padded():
    assert format_idno("ulb_x_{counter:05d}", 1, "object") == "ulb_x_00001"
    assert format_idno("ulb_x_{counter:05d}", 999, "object") == "ulb_x_00999"


def test_format_idno_year():
    result = format_idno("PA-{year}-{counter:04d}", 7, "object", year=2026)
    assert result == "PA-2026-0007"


def test_format_idno_type_placeholder():
    assert format_idno("{type}_{counter}", 3, "object") == "obj_3"
    assert format_idno("{type}_{counter}", 3, "entity") == "ent_3"
    assert format_idno("{type}_{counter}", 3, "place") == "pla_3"
    assert format_idno("{type}_{counter}", 3, "occurrence") == "occ_3"


def test_format_idno_combined():
    result = format_idno("{type}-{year}-{counter:04d}", 42, "entity", year=2025)
    assert result == "ent-2025-0042"


def test_format_idno_unknown_type_abbreviates():
    result = format_idno("{type}_{counter}", 1, "custom_record_type")
    assert result == "cus_1"


# ---------------------------------------------------------------------------
# validate_idno_pattern
# ---------------------------------------------------------------------------

def test_valid_pattern_matches():
    assert validate_idno_pattern(r"^ulb_x_\d{5}$", "ulb_x_00001") is True


def test_valid_pattern_no_match():
    assert validate_idno_pattern(r"^ulb_x_\d{5}$", "ulb_x_1") is False
    assert validate_idno_pattern(r"^ulb_x_\d{5}$", "PA-2026-0001") is False


def test_invalid_regex_returns_true():
    assert validate_idno_pattern(r"[invalid(", "anything") is True


# ---------------------------------------------------------------------------
# peek_next_idno
# ---------------------------------------------------------------------------

def _make_db(current_value: int | None) -> AsyncMock:
    row = (current_value,) if current_value is not None else None
    fetch_result = MagicMock()
    fetch_result.fetchone.return_value = row
    db = AsyncMock()
    db.execute = AsyncMock(return_value=fetch_result)
    return db


@pytest.mark.asyncio
async def test_peek_next_idno_from_zero():
    db = _make_db(0)
    result = await peek_next_idno(db, "object", "ulb_x_{counter:05d}")
    assert result == "ulb_x_00001"


@pytest.mark.asyncio
async def test_peek_next_idno_increments_by_one():
    db = _make_db(5)
    result = await peek_next_idno(db, "object", "ulb_x_{counter:05d}")
    assert result == "ulb_x_00006"


@pytest.mark.asyncio
async def test_peek_next_idno_no_row_starts_at_one():
    db = _make_db(None)
    result = await peek_next_idno(db, "object", "obj_{counter}")
    assert result == "obj_1"


# ---------------------------------------------------------------------------
# maybe_advance_counter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_maybe_advance_counter_matching_idno_executes_upsert():
    db = _make_db(4)
    await maybe_advance_counter(db, "object", "ulb_x_{counter:05d}", "ulb_x_00005")
    assert db.execute.call_count == 2  # one SELECT for current, one INSERT/UPDATE


@pytest.mark.asyncio
async def test_maybe_advance_counter_non_matching_idno_skips_upsert():
    db = _make_db(4)
    await maybe_advance_counter(db, "object", "ulb_x_{counter:05d}", "manual_id_xyz")
    assert db.execute.call_count == 1  # only the SELECT
