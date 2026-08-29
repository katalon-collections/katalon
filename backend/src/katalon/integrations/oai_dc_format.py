from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.metadata_format import MetadataFormat
from katalon.services.metadata_mapping_service import extract_values

DC_NS = "http://purl.org/dc/elements/1.1/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

OAI_DC_TARGETS = {
    "dc:title",
    "dc:creator",
    "dc:subject",
    "dc:description",
    "dc:publisher",
    "dc:contributor",
    "dc:date",
    "dc:type",
    "dc:format",
    "dc:identifier",
    "dc:source",
    "dc:language",
    "dc:relation",
    "dc:coverage",
    "dc:rights",
}


class OaiDcFormat(MetadataFormat):
    key = "oai_dc"
    label = "OAI Dublin Core"
    targets = OAI_DC_TARGETS
    schema_url = "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
    namespace = "http://www.openarchives.org/OAI/2.0/oai_dc/"

    def render(self, hit: dict[str, Any], mappings: dict[str, list[str]]) -> ET.Element:
        src = hit["_source"]
        record_id = hit["_id"]
        record_type = src.get("record_type", "")
        md: dict[str, Any] = src.get("metadata", {})

        dc = ET.Element("oai_dc:dc", {
            "xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
            "xmlns:dc": DC_NS,
            "xmlns:xsi": XSI_NS,
            "xsi:schemaLocation": (
                "http://www.openarchives.org/OAI/2.0/oai_dc/ "
                "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
            ),
        })

        mapped_targets: set[str] = set()
        for field_name, target_paths in mappings.items():
            for value in extract_values(src, field_name):
                for target_path in target_paths:
                    mapped_targets.add(target_path)
                    if target_path.startswith("dc:"):
                        ET.SubElement(dc, target_path).text = value

        if "dc:type" not in mapped_targets:
            ET.SubElement(dc, "dc:type").text = record_type

        ET.SubElement(dc, "dc:identifier").text = f"oai:katalon:{record_type}:{record_id}"
        if idno := src.get("idno") or md.get("idno"):
            ET.SubElement(dc, "dc:identifier").text = str(idno)

        return dc
