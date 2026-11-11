# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "lido_demo_schema.yaml"


async def _import(client, headers, **params):
    return await client.post(
        "/v1/schema/import",
        headers=headers,
        params=params,
        files={"file": ("schema.yaml", FIXTURE.read_bytes(), "application/x-yaml")},
    )


@pytest.mark.asyncio
async def test_schema_yaml_creates_groups_vocabularies_and_relation_fields(
    async_client, auth_headers
) -> None:
    dry = await _import(async_client, auth_headers, dry_run="true")
    assert dry.status_code == 200, dry.text
    assert dry.json()["errors"] == []
    # The dry run wrote nothing.
    before = await async_client.get("/v1/schema/object", headers=auth_headers)
    assert "masse" not in [f["name"] for f in before.json()]

    first = await _import(async_client, auth_headers)
    assert first.status_code == 200, first.text
    assert first.json()["errors"] == []

    fields = {f["name"]: f for f in (await async_client.get("/v1/schema/object", headers=auth_headers)).json()}
    assert [c["name"] for c in fields["masse"]["children"]] == ["typ", "wert", "einheit"]
    vocabs = {v["name"]: v["id"] for v in (await async_client.get("/v1/vocabularies", headers=auth_headers)).json()}
    assert fields["material"]["settings"]["vocabulary_id"] == vocabs["material"]
    assert fields["fundort"]["settings"]["fixed_relation_type"] == "found_at"
    assert fields["fundort"]["settings"]["relation_type_vocab"] == vocabs["relation_types"]
    collection = [f["name"] for f in (await async_client.get("/v1/schema/collection", headers=auth_headers)).json()]
    assert "leitung" in collection

    # Running it again changes nothing.
    again = await _import(async_client, auth_headers)
    body = again.json()
    assert (body["created"], body["updated"]) == (0, 0)
    assert body["skipped"] > 0
