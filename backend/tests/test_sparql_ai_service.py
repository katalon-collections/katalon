# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from katalon.services.sparql_ai_service import _extract_json, generate_sparql_from_prompt


def test_extract_json_direct() -> None:
    text = '{"sparql": "SELECT * WHERE { ?s ?p ?o }", "explanation": "Test query"}'
    res = _extract_json(text)
    assert res["sparql"] == "SELECT * WHERE { ?s ?p ?o }"
    assert res["explanation"] == "Test query"


def test_extract_json_markdown_fences() -> None:
    text = '```json\n{"sparql": "SELECT ?s WHERE { ?s a crm:E22_Human_Made_Object }", "explanation": "Objekte"}\n```'
    res = _extract_json(text)
    assert "crm:E22_Human_Made_Object" in res["sparql"]
    assert res["explanation"] == "Objekte"


def test_extract_json_raw_sparql_fallback() -> None:
    text = "```sparql\nSELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10\n```"
    res = _extract_json(text)
    assert "SELECT ?s ?p ?o" in res["sparql"]
    assert "explanation" in res


def test_extract_json_invalid() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _extract_json("Random prose without any SPARQL query keywords")
    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_generate_sparql_prompt_validation() -> None:
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    with pytest.raises(HTTPException) as exc_empty:
        await generate_sparql_from_prompt(mock_db, user_id, "   ")
    assert exc_empty.value.status_code == 422

    with pytest.raises(HTTPException) as exc_long:
        await generate_sparql_from_prompt(mock_db, user_id, "x" * 2001)
    assert exc_long.value.status_code == 422


@pytest.mark.asyncio
async def test_generate_sparql_success() -> None:
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    user_id = uuid.uuid4()
    mock_config = AsyncMock()
    mock_config.ai_model = "gpt-4.1-mini"
    mock_config.ai_max_output_tokens = 800

    fake_ai_resp = {
        "choices": [
            {
                "message": {
                    "content": '{"sparql": "SELECT ?s WHERE { ?s a crm:E21_Person } LIMIT 10", "explanation": "Personen"}'
                }
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 45},
    }

    with (
        patch("katalon.services.sparql_ai_service.ensure_ai_allowed", new_callable=AsyncMock, return_value=mock_config),
        patch("katalon.services.sparql_ai_service.get_secret", new_callable=AsyncMock, return_value="fake-key"),
        patch("katalon.services.sparql_ai_service.call_ai_provider", new_callable=AsyncMock, return_value=fake_ai_resp),
        patch("katalon.services.sparql_ai_service.log_change", new_callable=AsyncMock),
    ):
        res = await generate_sparql_from_prompt(mock_db, user_id, "Zeige Personen")
        assert res["sparql"] == "SELECT ?s WHERE { ?s a crm:E21_Person } LIMIT 10"
        assert res["explanation"] == "Personen"


@pytest.mark.asyncio
async def test_generate_sparql_rejects_invalid_ast() -> None:
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    mock_config = AsyncMock()
    mock_config.ai_model = "gpt-4.1-mini"
    mock_config.ai_max_output_tokens = 800

    # LLM returns invalid SPARQL update query
    fake_ai_resp = {
        "choices": [
            {
                "message": {
                    "content": '{"sparql": "DELETE WHERE { ?s ?p ?o }", "explanation": "Dangerous delete"}'
                }
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }

    with (
        patch("katalon.services.sparql_ai_service.ensure_ai_allowed", new_callable=AsyncMock, return_value=mock_config),
        patch("katalon.services.sparql_ai_service.get_secret", new_callable=AsyncMock, return_value="fake-key"),
        patch("katalon.services.sparql_ai_service.call_ai_provider", new_callable=AsyncMock, return_value=fake_ai_resp),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await generate_sparql_from_prompt(mock_db, user_id, "Lösche alle Daten")
        assert exc_info.value.status_code == 502
        assert "syntaktisch fehlerhaft" in exc_info.value.detail
