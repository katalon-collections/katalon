from __future__ import annotations

from dataclasses import dataclass

import pytest

import katalon.main as main_module


@dataclass
class _ScalarResult:
    value: object | None

    def scalar_one_or_none(self) -> object | None:
        return self.value


class _FakeDB:
    def __init__(self, existing_user: object | None) -> None:
        self.existing_user = existing_user
        self.added = None
        self.committed = False

    async def execute(self, _query) -> _ScalarResult:
        return _ScalarResult(self.existing_user)

    def add(self, value) -> None:
        self.added = value

    async def commit(self) -> None:
        self.committed = True


class _FakeSessionContext:
    def __init__(self, db: _FakeDB) -> None:
        self._db = db

    async def __aenter__(self) -> _FakeDB:
        return self._db

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_ensure_admin_creates_superuser_from_base_url(monkeypatch, tmp_path) -> None:
    fake_db = _FakeDB(existing_user=None)
    credentials_path = tmp_path / "first-run-credentials.txt"

    monkeypatch.setattr(main_module, "AsyncSessionLocal", lambda: _FakeSessionContext(fake_db))
    monkeypatch.setattr(
        main_module.settings,
        "katalon_base_url",
        "https://katalon.example.org",
        raising=False,
    )
    monkeypatch.setattr(
        main_module.settings,
        "first_run_credentials_path",
        str(credentials_path),
        raising=False,
    )
    monkeypatch.setattr(
        main_module.settings,
        "default_admin_email",
        "admin@fallback.test",
        raising=False,
    )
    monkeypatch.setattr(
        main_module.settings,
        "default_admin_password",
        "fallback-password",
        raising=False,
    )
    monkeypatch.setattr(main_module.secrets, "token_urlsafe", lambda _n: "A1B2C3D4E5F6G7H8I9J0")
    monkeypatch.setattr(main_module, "hash_password", lambda value: f"hashed::{value}")

    await main_module._ensure_admin()

    assert fake_db.committed is True
    assert fake_db.added is not None
    assert fake_db.added.email == "admin@katalon.example.org"
    assert fake_db.added.role == "superuser"
    assert fake_db.added.hashed_password == "hashed::A1B2C3D4E5F6G7H8I9J0"
    assert credentials_path.exists()
    assert "Email: admin@katalon.example.org" in credentials_path.read_text(encoding="utf-8")
    assert "Password: A1B2C3D4E5F6G7H8I9J0" in credentials_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_ensure_admin_is_one_shot_when_superuser_exists(monkeypatch, tmp_path) -> None:
    fake_db = _FakeDB(existing_user=object())
    credentials_path = tmp_path / "first-run-credentials.txt"

    monkeypatch.setattr(main_module, "AsyncSessionLocal", lambda: _FakeSessionContext(fake_db))
    monkeypatch.setattr(
        main_module.settings,
        "katalon_base_url",
        "https://katalon.example.org",
        raising=False,
    )
    monkeypatch.setattr(
        main_module.settings,
        "first_run_credentials_path",
        str(credentials_path),
        raising=False,
    )

    await main_module._ensure_admin()

    assert fake_db.added is None
    assert fake_db.committed is False
    assert not credentials_path.exists()
