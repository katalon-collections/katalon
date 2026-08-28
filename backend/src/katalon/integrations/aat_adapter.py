from __future__ import annotations

import httpx

from .authority import AuthorityHit, AuthoritySource

_SPARQL = "https://vocab.getty.edu/sparql.json"


class AATAdapter(AuthoritySource):
    source_id = "aat"

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        sparql = (
            "SELECT ?concept ?label WHERE {"
            "  ?concept a skos:Concept ;"
            "           skos:inScheme <http://vocab.getty.edu/aat/> ;"
            "           rdfs:label ?label ."
            f'  FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{query}")))'
            f"}} LIMIT {limit}"
        )
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(_SPARQL, params={"query": sparql})
            r.raise_for_status()
            data = r.json()
        hits: list[AuthorityHit] = []
        for row in data.get("results", {}).get("bindings", []):
            uri = row.get("concept", {}).get("value", "")
            aat_id = uri.split("/")[-1] if uri else ""
            label = row.get("label", {}).get("value", "")
            hits.append(AuthorityHit(
                source=self.source_id,
                external_id=aat_id,
                label=label,
                description="",
                extra={"uri": uri},
            ))
        return hits

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        uri = f"https://vocab.getty.edu/aat/{external_id}.json"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(uri)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
        label = ""
        graph = data if isinstance(data, list) else data.get("@graph", [])
        for node in graph:
            if node.get("@id", "").endswith(f"/{external_id}"):
                pref = node.get("skos:prefLabel", {})
                if isinstance(pref, list):
                    label = next((p.get("@value", "") for p in pref if p.get("@language") in ("de", "en")), "")
                elif isinstance(pref, dict):
                    label = pref.get("@value", "")
                break
        return AuthorityHit(
            source=self.source_id,
            external_id=external_id,
            label=label,
            description="",
            extra={"uri": f"https://vocab.getty.edu/aat/{external_id}"},
        )
