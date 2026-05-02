from __future__ import annotations

import httpx

from .authority import AuthorityHit, AuthoritySource


class ICONCLASSAdapter(AuthoritySource):
    source_id = "iconclass"
    BASE = "https://iconclass.org"

    def __init__(self, language: str = "de") -> None:
        self.language = language

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self.BASE}/search",
                params={"q": query, "lang": self.language, "format": "json"},
            )
            r.raise_for_status()
            data = r.json()
        hits: list[AuthorityHit] = []
        for notation in (data.get("result") or [])[:limit]:
            label = notation  # plain notation; detail fetched separately
            # Search result only gives notations; fetch text for each (up to 5)
            if len(hits) < 5:
                detail = await self._fetch_notation(notation)
                if detail:
                    hits.append(detail)
                    continue
            hits.append(AuthorityHit(
                source=self.source_id,
                external_id=notation,
                label=notation,
                description="",
                extra={"uri": f"{self.BASE}/{notation}"},
            ))
        return hits

    async def _fetch_notation(self, notation: str) -> AuthorityHit | None:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.BASE}/{notation}.json")
            if r.status_code != 200:
                return None
            data = r.json()
        txt = data.get("txt", {})
        label_list = txt.get(self.language) or txt.get("en") or []
        label = label_list[0] if label_list else notation
        return AuthorityHit(
            source=self.source_id,
            external_id=notation,
            label=label,
            description=", ".join(data.get("kw", {}).get(self.language, [])[:3]),
            extra={"uri": f"{self.BASE}/{notation}", "broader": data.get("p", [])},
        )

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        return await self._fetch_notation(external_id)
