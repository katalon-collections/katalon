# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import pytest

from katalon.services.importer.formats.xml_format import XmlFormat


def test_xml_parser_rejects_external_entities() -> None:
    content = b"""<?xml version="1.0"?>
<!DOCTYPE data [
<!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<data><record><title>&xxe;</title></record></data>
"""

    rows = list(XmlFormat().parse_flat(content, record_xpath="record"))

    assert rows == [{}]


def test_xml_parser_rejects_too_deep_documents() -> None:
    content = ("<a>" * 70 + "x" + "</a>" * 70).encode()

    with pytest.raises(ValueError, match="zu tief"):
        XmlFormat().list_element_levels(content)
