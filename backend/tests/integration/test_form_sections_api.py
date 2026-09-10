# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_form_sections_accept_partial_field_assignment(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await async_client.post(
        "/v1/form-sections",
        headers=auth_headers,
        json={"target_type": "object", "label": {"de": "Beschreibung"}, "field_names": ["label"]},
    )
    assert response.status_code == 201
    section_id = response.json()["id"]

    listed = await async_client.get("/v1/form-sections?target_type=object", headers=auth_headers)
    assert listed.status_code == 200
    assert any(section["id"] == section_id for section in listed.json())

    deleted = await async_client.delete(f"/v1/form-sections/{section_id}", headers=auth_headers)
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_form_sections_reject_duplicate_field_assignment(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await async_client.post(
        "/v1/form-sections",
        headers=auth_headers,
        json={"target_type": "object", "label": {"de": "Doppelt"}, "field_names": ["label", "label"]},
    )
    assert response.status_code == 422
