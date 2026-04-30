from __future__ import annotations

from katalon.integrations.authority import AuthorityHit, AuthoritySource
from katalon.integrations.gnd_adapter import GNDAdapter
from katalon.integrations.geonames_adapter import GeonamesAdapter

_ADAPTERS: dict[str, AuthoritySource] = {
    "gnd": GNDAdapter(),
    "geonames": GeonamesAdapter(),
}


def list_sources() -> list[str]:
    return list(_ADAPTERS.keys())


async def search(source_id: str, query: str, limit: int = 10) -> list[AuthorityHit]:
    adapter = _ADAPTERS.get(source_id)
    if not adapter:
        return []
    return await adapter.search(query, limit)


async def fetch(source_id: str, external_id: str) -> AuthorityHit | None:
    adapter = _ADAPTERS.get(source_id)
    if not adapter:
        return None
    return await adapter.fetch(external_id)
