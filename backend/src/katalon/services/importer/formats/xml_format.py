from typing import Iterator

from .base import Selector, SourceFormat, SourceRecord


class XmlFormat(SourceFormat):
    """XML file format handler (stub for Phase D)."""

    def sniff(self, content: bytes, filename: str) -> bool:
        """Match .xml files."""
        return filename.lower().endswith(".xml")

    def parse(self, content: bytes) -> Iterator[SourceRecord]:
        """Parse XML (not yet implemented)."""
        raise NotImplementedError("XML import support is planned for Phase D")

    def list_selectors(self, content: bytes) -> list[Selector]:
        """List available XML paths (not yet implemented)."""
        raise NotImplementedError("XML import support is planned for Phase D")
