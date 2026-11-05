# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin
"""Template implementation for a custom Katalon authority adapter."""

from __future__ import annotations

from typing import Any

import httpx

try:
    from katalon.config import settings
    from katalon.integrations.authority import AuthorityHit, AuthoritySource
except ImportError:
    from abc import ABC, abstractmethod
    from dataclasses import dataclass, field

    @dataclass
    class AuthorityHit:
        source: str
        external_id: str
        label: str
        description: str = ""
        extra: dict[str, Any] = field(default_factory=dict[str, Any])

    class AuthoritySource(ABC):
        source_id: str

        @abstractmethod
        async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]: ...

        @abstractmethod
        async def fetch(self, external_id: str) -> AuthorityHit | None: ...

    settings = None


class TemplateAdapter(AuthoritySource):
    source_id: str = "template-source"

    def __init__(
        self,
        source_id: str = "template-source",
        api_base_url: str = "https://api.example.org",
        api_key: str = "",
        timeout: float = 10.0,
    ) -> None:
        self.source_id = source_id
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        # Respectful User-Agent for GLAM APIs
        headers["User-Agent"] = (
            "Katalon-CustomAdapter/1.0 (https://github.com/katalon-collections/katalon; admin@localhost)"
        )
        return headers

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        if not query.strip():
            return []

        url = f"{self.api_base_url}/search"
        params = {"q": query.strip(), "limit": limit}

        async with httpx.AsyncClient(
            timeout=self.timeout, headers=self._headers()
        ) as client:
            r = await client.get(url, params=params)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            data = r.json()

        hits: list[AuthorityHit] = []
        for item in data.get("results", []):
            hits.append(
                AuthorityHit(
                    source=self.source_id,
                    external_id=str(item.get("id")),
                    label=str(item.get("name") or item.get("title")),
                    description=str(item.get("description") or ""),
                    extra={"uri": f"{self.api_base_url}/record/{item.get('id')}"},
                )
            )
        return hits

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        if not external_id.strip():
            return None

        url = f"{self.api_base_url}/record/{external_id.strip()}"
        async with httpx.AsyncClient(
            timeout=self.timeout, headers=self._headers()
        ) as client:
            r = await client.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            item = r.json()

        return AuthorityHit(
            source=self.source_id,
            external_id=external_id,
            label=str(item.get("name") or item.get("title")),
            description=str(item.get("description") or ""),
            extra={"uri": url},
        )
