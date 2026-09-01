# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import httpx

from katalon.config import settings

from .authority import AuthorityHit, AuthoritySource

GEONAMES_SEARCH = "http://api.geonames.org/searchJSON"
GEONAMES_GET = "http://api.geonames.org/getJSON"


def _raise_for_api_status(data: dict[object, object]) -> None:
    status = data.get("status")
    if isinstance(status, dict):
        message = status.get("message", "Unbekannter Fehler")
        raise httpx.HTTPError(f"GeoNames API: {message}")


class GeonamesAdapter(AuthoritySource):
    source_id = "geonames"

    def _username(self) -> str:
        return getattr(settings, "geonames_username", "demo")

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(GEONAMES_SEARCH, params={
                "q": query,
                "maxRows": limit,
                "type": "json",
                "username": self._username(),
            })
            r.raise_for_status()
            data = r.json()
        _raise_for_api_status(data)
        hits: list[AuthorityHit] = []
        for item in data.get("geonames", []):
            gid = str(item.get("geonameId", ""))
            label = item.get("name", "")
            country = item.get("countryName", "")
            fcl = item.get("fclName", "")
            hits.append(AuthorityHit(
                source=self.source_id,
                external_id=gid,
                label=label,
                description=f"{fcl}, {country}".strip(", "),
                extra={"lat": item.get("lat"), "lng": item.get("lng"), "fcl": item.get("fcl")},
            ))
        return hits

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(GEONAMES_GET, params={
                "geonameId": external_id,
                "username": self._username(),
            })
            if r.status_code == 404:
                return None
            r.raise_for_status()
            item = r.json()
        _raise_for_api_status(item)
        return AuthorityHit(
            source=self.source_id,
            external_id=external_id,
            label=item.get("name", ""),
            description=item.get("fclName", ""),
            extra={"lat": item.get("lat"), "lng": item.get("lng"), "countryName": item.get("countryName")},
        )
