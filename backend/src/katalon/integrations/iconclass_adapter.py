# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import asyncio
import re

import httpx

from .authority import AuthorityHit, AuthoritySource


class ICONCLASSAdapter(AuthoritySource):
    source_id = "iconclass"
    BASE = "https://iconclass.org"
    # Later configurable per source; currently preserves the established catalogue policy.
    BLOCKED_PREFIXES = ("1", "9")

    def __init__(self, language: str = "de") -> None:
        self.language = language

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{self.BASE}/api/search",
                params={
                    "q": query,
                    "lang": self.language,
                    "size": min(max(limit * 5, 10), 50),
                    "page": 1,
                    "sort": "rank",
                    "keys": 0,
                },
            )
            r.raise_for_status()
            data = r.json()
        notations = [
            str(notation)
            for notation in data.get("result") or []
            if str(notation)[:1] not in self.BLOCKED_PREFIXES
        ]
        hits = [hit for hit in await asyncio.gather(*(self._fetch_notation(n) for n in notations)) if hit]
        query_lc = query.strip().casefold()
        hits.sort(key=lambda hit: (self._lexical_rank(hit.extra.get("_labels", []), query_lc), self._notation_depth(hit.external_id)))
        for hit in hits:
            hit.extra.pop("_labels", None)
        return hits[:limit]

    async def _fetch_notation(self, notation: str) -> AuthorityHit | None:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.BASE}/{notation}.json")
            if r.status_code != 200:
                return None
            data = r.json()
        txt = data.get("txt", {})
        labels = [
            label
            for value in txt.values()
            for label in (value if isinstance(value, list) else [value])
            if isinstance(label, str)
        ]
        preferred = txt.get(self.language) or txt.get("en") or labels
        label = preferred[0] if isinstance(preferred, list) and preferred else preferred if isinstance(preferred, str) else notation
        return AuthorityHit(
            source=self.source_id,
            external_id=notation,
            label=label,
            description=", ".join(data.get("kw", {}).get(self.language, [])[:3]),
            extra={"uri": f"{self.BASE}/{notation}", "broader": data.get("p", []), "_labels": labels},
        )

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        hit = await self._fetch_notation(external_id)
        if hit:
            hit.extra.pop("_labels", None)
        return hit

    @staticmethod
    def _lexical_rank(labels: object, query: str) -> int:
        if not isinstance(labels, list):
            return 4
        ranks = []
        for label in labels:
            if not isinstance(label, str):
                continue
            value = label.strip().casefold()
            if value == query:
                ranks.append(0)
            elif value.startswith(query):
                ranks.append(1)
            elif re.search(rf"\b{re.escape(query)}\b", value):
                ranks.append(2)
            elif query in value:
                ranks.append(3)
            else:
                ranks.append(4)
        return min(ranks, default=4)

    @staticmethod
    def _notation_depth(notation: str) -> int:
        base = re.sub(r"\([^)]*\)", "", notation).strip()
        return max(0, len(base) - 1) + len(re.findall(r"\([^)]*\)", notation))
