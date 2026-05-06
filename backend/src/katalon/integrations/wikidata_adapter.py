from __future__ import annotations

import httpx

from .authority import AuthorityHit, AuthoritySource


class WikidataAdapter(AuthoritySource):
    source_id = "wikidata"

    _headers = {"User-Agent": "Katalon/1.0 (https://github.com/your-org/katalon; contact@example.org) httpx"}

    async def search(self, query: str, limit: int = 10, language: str = "de") -> list[AuthorityHit]:
        async with httpx.AsyncClient(timeout=10, headers=self._headers) as client:
            r = await client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbsearchentities",
                    "search": query,
                    "language": language,
                    "type": "item",
                    "limit": limit,
                    "format": "json",
                },
            )
            if r.status_code != 200:
                return []
            data = r.json()
        hits: list[AuthorityHit] = []
        for item in data.get("search", []):
            qid = item.get("id", "")
            hits.append(AuthorityHit(
                source=self.source_id,
                external_id=qid,
                label=item.get("label", ""),
                description=item.get("description", ""),
                extra={"uri": f"https://www.wikidata.org/wiki/{qid}"},
            ))
        return hits

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        async with httpx.AsyncClient(timeout=10, headers=self._headers) as client:
            r = await client.get(
                f"https://www.wikidata.org/wiki/Special:EntityData/{external_id}.json",
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
        entity = data.get("entities", {}).get(external_id, {})
        labels = entity.get("labels", {})
        label = (labels.get("de") or labels.get("en") or next(iter(labels.values()), {})).get("value", "")
        descriptions = entity.get("descriptions", {})
        desc = (descriptions.get("de") or descriptions.get("en") or next(iter(descriptions.values()), {})).get("value", "")
        return AuthorityHit(
            source=self.source_id,
            external_id=external_id,
            label=label,
            description=desc,
            extra={"uri": f"https://www.wikidata.org/wiki/{external_id}"},
        )
