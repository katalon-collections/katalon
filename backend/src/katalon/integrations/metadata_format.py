from __future__ import annotations

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any


class MetadataFormat(ABC):
    key: str
    label: str
    targets: set[str]
    schema_url: str
    namespace: str

    @abstractmethod
    def render(self, hit: dict[str, Any], mappings: dict[str, list[str]]) -> ET.Element:
        """Render one ES hit into a format-specific XML element, using field_name -> target_paths mappings."""


def append_path(root: ET.Element, path: str, value: str) -> None:
    """Create the nested element chain for a slash-separated target_path and set the leaf text."""
    if not value:
        return
    parts = path.split("/")
    el = root
    for part in parts[:-1]:
        el = ET.SubElement(el, part)
    ET.SubElement(el, parts[-1]).text = value
