"""Unit tests for banner Pydantic schemas and color validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from katalon.api.v1.banners import VALID_COLORS, BannerCreate, BannerUpdate


def test_banner_create_defaults() -> None:
    b = BannerCreate(message="Maintenance tonight")
    assert b.color == "blue"
    assert b.show_admin is True
    assert b.show_portal is True
    assert b.is_active is True
    assert b.expires_at is None


def test_banner_create_valid_colors() -> None:
    for color in VALID_COLORS:
        b = BannerCreate(message="Test", color=color)
        assert b.color == color


def test_banner_create_missing_message() -> None:
    with pytest.raises(ValidationError):
        BannerCreate()  # type: ignore[call-arg]


def test_banner_update_partial() -> None:
    u = BannerUpdate(is_active=False)
    data = u.model_dump(exclude_none=True)
    assert data == {"is_active": False}


def test_banner_update_empty() -> None:
    u = BannerUpdate()
    assert u.model_dump(exclude_none=True) == {}
