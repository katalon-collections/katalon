"""Optimistic-locking version check (issue #272)."""
import pytest
from fastapi import HTTPException

from katalon.core.concurrency import check_version


def test_no_if_match_skips_check() -> None:
    # Clients that do not send If-Match (importer, scripts) keep working.
    check_version(current_version=5, if_match=None)


def test_matching_version_passes() -> None:
    check_version(current_version=5, if_match=5)


def test_stale_version_raises_409() -> None:
    with pytest.raises(HTTPException) as exc:
        check_version(current_version=6, if_match=3)
    assert exc.value.status_code == 409
    assert exc.value.detail == {"error": "version_conflict", "current_version": 6}
