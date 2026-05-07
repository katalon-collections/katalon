from __future__ import annotations

from urllib.parse import quote

import httpx

from katalon.config import settings


class DnbUrnAdapterError(Exception):
    pass


class DnbUrnAdapter:
    def __init__(self) -> None:
        self.base_url = settings.dnb_urn_api_url.rstrip("/")
        self.namespace = settings.dnb_urn_namespace
        self.username = settings.dnb_urn_username
        self.password = settings.dnb_urn_password

    def ensure_configured(self) -> None:
        if not settings.dnb_urn_enabled:
            raise DnbUrnAdapterError("DNB-URN ist deaktiviert.")
        if not self.namespace or not self.username or not self.password:
            raise DnbUrnAdapterError(
                "DNB-URN ist unvollständig konfiguriert. "
                "Bitte DNB_URN_NAMESPACE, DNB_URN_USERNAME und DNB_URN_PASSWORD setzen."
            )

    async def suggest_urn(self) -> str:
        self.ensure_configured()
        namespace = quote(self.namespace, safe="")
        url = f"{self.base_url}/namespaces/name/{namespace}/urn-suggestion"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, auth=(self.username, self.password))
            response.raise_for_status()
        data = response.json()
        urn = data.get("suggestedUrn")
        if not isinstance(urn, str) or not urn:
            raise DnbUrnAdapterError("DNB-API lieferte keine gültige URN-Suggestion.")
        return urn

    async def register_urn(self, urn: str, target_url: str) -> str:
        self.ensure_configured()
        payload = {"urn": urn, "urls": [{"url": target_url, "priority": 10}]}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/urns",
                json=payload,
                auth=(self.username, self.password),
            )
            response.raise_for_status()
        data = response.json()
        registered = data.get("urn")
        if not isinstance(registered, str) or not registered:
            raise DnbUrnAdapterError("DNB-API lieferte keine registrierte URN zurück.")
        return registered

    async def mint_and_register(self, target_url: str) -> str:
        urn = await self.suggest_urn()
        return await self.register_urn(urn=urn, target_url=target_url)
