# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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
    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        ...

    @abstractmethod
    async def fetch(self, external_id: str) -> AuthorityHit | None:
        ...
