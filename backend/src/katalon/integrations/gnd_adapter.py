# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import httpx

from .authority import AuthorityHit, AuthoritySource

GND_SUGGEST = "https://lobid.org/gnd/search"
GND_FETCH = "https://lobid.org/gnd/{id}.json"


class GNDAdapter(AuthoritySource):
    source_id = "gnd"

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(GND_SUGGEST, params={"q": query, "size": limit, "format": "json"})
            r.raise_for_status()
            data = r.json()
        hits: list[AuthorityHit] = []
        for item in data.get("member", []):
            gnd_id = item.get("gndIdentifier", "")
            label = item.get("preferredName", "")
            desc_parts = item.get("professionOrOccupation", [])
            description = ", ".join(
                p.get("label", "") if isinstance(p, dict) else str(p)
                for p in desc_parts[:3]
            )
            hits.append(AuthorityHit(
                source=self.source_id,
                external_id=gnd_id,
                label=label,
                description=description,
                extra={"type": item.get("type", [])},
            ))
        return hits

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(GND_FETCH.format(id=external_id))
            if r.status_code == 404:
                return None
            r.raise_for_status()
            item = r.json()
        return AuthorityHit(
            source=self.source_id,
            external_id=external_id,
            label=item.get("preferredName", ""),
            description=item.get("biographicalOrHistoricalInformation", [""])[0]
            if item.get("biographicalOrHistoricalInformation") else "",
            extra=item,
        )
