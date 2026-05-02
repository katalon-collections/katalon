from __future__ import annotations

import httpx

from .authority import AuthorityHit, AuthoritySource

_SPARQL = "http://vocab.getty.edu/sparql.json"
_SPARQL_QUERY = """
SELECT ?place ?label ?lat ?long WHERE {{
  ?place a skos:Concept ;
         skos:inScheme tgn: ;
         skosxl:prefLabel/skosxl:literalForm ?label .
  FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{query}")))
  OPTIONAL {{ ?place wgs:lat ?lat ; wgs:long ?long }}
}} LIMIT {limit}
"""


class TGNAdapter(AuthoritySource):
    source_id = "tgn"

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        sparql = (
            "SELECT ?place ?label ?lat ?long WHERE {"
            "  ?place a skos:Concept ;"
            "         skos:inScheme <http://vocab.getty.edu/tgn/> ;"
            "         rdfs:label ?label ."
            f'  FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{query}")))'
            "  OPTIONAL { ?place <http://www.w3.org/2003/01/geo/wgs84_pos#lat> ?lat ;"
            "             <http://www.w3.org/2003/01/geo/wgs84_pos#long> ?long }"
            f"}} LIMIT {limit}"
        )
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(_SPARQL, params={"query": sparql})
            r.raise_for_status()
            data = r.json()
        hits: list[AuthorityHit] = []
        for row in data.get("results", {}).get("bindings", []):
            uri = row.get("place", {}).get("value", "")
            tgn_id = uri.split("/")[-1] if uri else ""
            label = row.get("label", {}).get("value", "")
            lat = row.get("lat", {}).get("value")
            lon = row.get("long", {}).get("value")
            hits.append(AuthorityHit(
                source=self.source_id,
                external_id=tgn_id,
                label=label,
                description="",
                extra={"uri": uri, "lat": lat, "lon": lon},
            ))
        return hits

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        uri = f"http://vocab.getty.edu/tgn/{external_id}.json"
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
            extra={"uri": f"https://vocab.getty.edu/tgn/{external_id}"},
        )
