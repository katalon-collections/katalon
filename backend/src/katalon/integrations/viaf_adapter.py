from __future__ import annotations

import httpx

from .authority import AuthorityHit, AuthoritySource


class VIAFAdapter(AuthoritySource):
    source_id = "viaf"

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://www.viaf.org/viaf/AutoSuggest",
                params={"query": query},
                headers={"Accept": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
        hits: list[AuthorityHit] = []
        for item in (data.get("result") or [])[:limit]:
            viaf_id = item.get("viafid", "")
            label = item.get("term", "")
            nametype = item.get("nametype", "")
            hits.append(AuthorityHit(
                source=self.source_id,
                external_id=viaf_id,
                label=label,
                description=nametype,
                extra={"uri": f"https://viaf.org/viaf/{viaf_id}"},
            ))
        return hits

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://www.viaf.org/viaf/{external_id}/viaf.json",
                headers={"Accept": "application/json"},
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            item = r.json()
        main_headings = item.get("mainHeadings", {}).get("data", [])
        label = ""
        if main_headings:
            first = main_headings[0]
            label = first.get("text", "") if isinstance(first, dict) else str(first)
        return AuthorityHit(
            source=self.source_id,
            external_id=external_id,
            label=label,
            description=item.get("nameType", ""),
            extra={"uri": f"https://viaf.org/viaf/{external_id}"},
        )
