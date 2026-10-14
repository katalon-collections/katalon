# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest


@pytest.mark.asyncio
async def test_portal_config_lists_facets_in_schema_order(async_client, auth_headers) -> None:
    prefix = f"ord_{uuid.uuid4().hex[:6]}"
    for name, sort_order in (("c", 300), ("a", 100), ("b", 200), ("a2", 200)):
        response = await async_client.post(
            "/v1/schema",
            headers=auth_headers,
            json={
                "target_type": "object",
                "name": f"{prefix}_{name}",
                "label": {"de": name},
                "field_type": "text",
                "is_facet": True,
                "show_in_detail": True,
                "sort_order": sort_order,
            },
        )
        assert response.status_code == 201, response.text

    config = await async_client.get("/v1/portal/config", headers=auth_headers)
    assert config.status_code == 200, config.text
    ours = [n for n in config.json()["facet_fields"]["object"] if n.startswith(prefix)]
    assert ours == [f"{prefix}_a", f"{prefix}_a2", f"{prefix}_b", f"{prefix}_c"]
