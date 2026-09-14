# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import httpx

from .authority import AuthorityHit, AuthoritySource

GND_SUGGEST = "https://lobid.org/gnd/search"
GND_FETCH = "https://lobid.org/gnd/{id}.json"


class GNDAdapter(AuthoritySource):
    source_id = "gnd"

    def __init__(self, filter_type: str | None = None, source_id: str = "gnd") -> None:
        self.filter_type = filter_type
        self.source_id = source_id

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        params: dict[str, str | int] = {"q": query, "size": limit, "format": "json"}
        if self.filter_type:
            params["filter"] = self.filter_type
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(GND_SUGGEST, params=params)
            r.raise_for_status()
            data = r.json()
        hits: list[AuthorityHit] = []
        for item in data.get("member", []):
            gnd_id = item.get("gndIdentifier", "")
            label = item.get("preferredName", "")
            desc_parts = item.get("professionOrOccupation") or item.get("gndSubjectCategory") or []
            if not isinstance(desc_parts, list):
                desc_parts = [desc_parts]
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
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(GND_FETCH.format(id=external_id))
            if r.status_code == 404:
                return None
            r.raise_for_status()
            item = r.json()
        return AuthorityHit(
            source=self.source_id,
            external_id=external_id,
            label=item.get("preferredName", ""),
            description=(
                (item.get("biographicalOrHistoricalInformation") or [""])[0]
                if item.get("biographicalOrHistoricalInformation")
                else (item.get("definition") or [""])[0]
                if item.get("definition")
                else ", ".join(
                    c.get("label", "") if isinstance(c, dict) else str(c)
                    for c in (item.get("gndSubjectCategory") or [])[:3]
                )
            ),
            extra=item,
        )
