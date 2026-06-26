from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

SourceRecord = dict[str, Any]


@dataclass
class Selector:
    path: str
    label: str
    sample: str
    kind: str  # "scalar" | "list" | "tree"


class SourceFormat(ABC):
    """Abstract base class for import format handlers (CSV, Excel, XML, etc)."""

    @abstractmethod
    def sniff(self, content: bytes, filename: str) -> bool:
        """Detect if this format can handle the given file."""

    @abstractmethod
    def parse(self, content: bytes) -> Iterator[SourceRecord]:
        """Parse content and yield rows as dicts. Headers become dict keys."""

    @abstractmethod
    def list_selectors(self, content: bytes) -> list[Selector]:
        """List available data paths/columns in the file."""
