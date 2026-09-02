# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.metadata_format import MetadataFormat, append_path
from katalon.services.metadata_mapping_service import extract_values

MODS_NS = "http://www.loc.gov/mods/v3"

# Pragmatic subset of MODS 3.x (the descriptive part METS wraps in dmdSec/mdWrap/xmlData).
# Extend via a metadata_formats DB row (config={"targets": [...]}) rather than forking this class.
MODS_TARGETS = {
    "mods:titleInfo/mods:title",
    "mods:name/mods:namePart",
    "mods:typeOfResource",
    "mods:originInfo/mods:dateCreated",
    "mods:abstract",
    "mods:accessCondition",
    "mods:identifier",
    "mods:language/mods:languageTerm",
}


class MetsModsFormat(MetadataFormat):
    key = "mets_mods"
    label = "METS/MODS"
    targets = MODS_TARGETS
    schema_url = "http://www.loc.gov/standards/mods/v3/mods-3-8.xsd"
    namespace = MODS_NS

    def render(self, hit: dict[str, Any], mappings: dict[str, list[str]]) -> ET.Element:
        record_id = hit["_id"]
        src = hit["_source"]

        root = ET.Element("mods:mods", {"xmlns:mods": MODS_NS, "ID": str(record_id)})

        for field_name, target_paths in mappings.items():
            for value in extract_values(src, field_name):
                for target_path in target_paths:
                    if target_path in self.targets:
                        append_path(root, target_path, value)

        return root
