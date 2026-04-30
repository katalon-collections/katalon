from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AuthorityHit:
    source: str
    external_id: str
    label: str
    description: str = ""
    extra: dict = field(default_factory=dict)


class AuthoritySource(ABC):
    source_id: str

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        ...

    @abstractmethod
    async def fetch(self, external_id: str) -> AuthorityHit | None:
        ...
