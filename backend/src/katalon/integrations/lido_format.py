from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.metadata_format import MetadataFormat, append_path
from katalon.services.metadata_mapping_service import extract_values

LIDO_NS = "http://www.lido-schema.org"

# Pragmatic subset of LIDO 1.1 covering the fields catalogers map most often.
# Extend via a metadata_formats DB row (config={"targets": [...]}) rather than forking this class.
LIDO_TARGETS = {
    "lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
    "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
    "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate",
    "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue",
    "lido:rightsWorkWrap/lido:rightsWorkSet/lido:rightsType/lido:term",
}


class LidoFormat(MetadataFormat):
    key = "lido"
    label = "LIDO"
    targets = LIDO_TARGETS
    schema_url = "http://www.lido-schema.org/schema/v1.1/lido-v1.1.xsd"
    namespace = LIDO_NS

    def render(self, hit: dict[str, Any], mappings: dict[str, list[str]]) -> ET.Element:
        record_id = hit["_id"]
        src = hit["_source"]

        root = ET.Element("lido:lido", {"xmlns:lido": LIDO_NS})
        ET.SubElement(root, "lido:lidoRecID").text = str(record_id)

        for field_name, target_paths in mappings.items():
            for value in extract_values(src, field_name):
                for target_path in target_paths:
                    if target_path in self.targets:
                        append_path(root, target_path, value)

        return root
