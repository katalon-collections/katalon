import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from katalon.config import Settings
from katalon.main import _check_production_secrets
from katalon.services.relation_type_service import sync_relation_type_terms


def _mock_scalars_result(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_sync_relation_type_terms_adds_missing_terms() -> None:
    vocab = MagicMock(id=uuid.uuid4())
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[
        _mock_scalars_result(["contains"]),
        _mock_scalars_result(["contains", "is platformversion of", "", None]),
    ])
    added = []
    db.add.side_effect = added.append

    await sync_relation_type_terms(db, vocab)

    assert len(added) == 1
    assert added[0].term == "is platformversion of"
    assert added[0].label == {"de": "is platformversion of", "en": "is platformversion of"}
    assert added[0].inverse_label == {}


def test_settings_require_katalon_secrets_key() -> None:
    with pytest.raises(ValidationError, match="katalon_secrets_key"):
        Settings(katalon_secrets_key="short")


def test_check_production_secrets_accepts_valid_katalon_secrets_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("katalon.main.settings.debug", False)
    monkeypatch.setattr("katalon.main.settings.secret_key", "x" * 32)
    monkeypatch.setattr("katalon.main.settings.katalon_secrets_key", "y" * 32)
    monkeypatch.setattr("katalon.main.settings.default_admin_password", "correct-horse-battery-staple")

    _check_production_secrets()
