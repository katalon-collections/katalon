"""Tests for XmlFormat: sniff, list_element_levels, parse, list_selectors."""
from katalon.services.importer.formats.xml_format import XmlFormat

fmt = XmlFormat()

# ── fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<collection>
  <record>
    <title>Foto 1</title>
    <creator>Maier</creator>
    <date>1920</date>
  </record>
  <record>
    <title>Foto 2</title>
    <creator>Huber</creator>
  </record>
</collection>
"""

MODS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<mods:modsCollection xmlns:mods="http://www.loc.gov/mods/v3">
  <mods:mods>
    <mods:titleInfo>
      <mods:title>Strassenbahn Muenchen</mods:title>
    </mods:titleInfo>
    <mods:name type="personal">
      <mods:namePart>Huber, Karl</mods:namePart>
    </mods:name>
    <mods:originInfo>
      <mods:dateIssued>1930</mods:dateIssued>
    </mods:originInfo>
  </mods:mods>
  <mods:mods>
    <mods:titleInfo>
      <mods:title>Bahnhof Frankfurt</mods:title>
    </mods:titleInfo>
  </mods:mods>
</mods:modsCollection>
"""

DC_XML = b"""<?xml version="1.0"?>
<records xmlns:dc="http://purl.org/dc/elements/1.1/">
  <record>
    <dc:title>Item A</dc:title>
    <dc:creator>Smith</dc:creator>
  </record>
  <record>
    <dc:title>Item B</dc:title>
  </record>
</records>
"""


# ── sniff ──────────────────────────────────────────────────────────────────────

def test_sniff_xml_extension():
    assert fmt.sniff(b"", "export.xml") is True


def test_sniff_xml_magic_bytes():
    assert fmt.sniff(b"<?xml version='1.0'?><root/>", "data.txt") is True


def test_sniff_xml_bare_tag():
    assert fmt.sniff(b"<collection><item/></collection>", "data") is True


def test_sniff_rejects_csv():
    assert fmt.sniff(b"title,creator\nFoo,Bar", "data.csv") is False


def test_sniff_rejects_html():
    assert fmt.sniff(b"<!DOCTYPE html><html/>", "page.html") is False


# ── list_element_levels ────────────────────────────────────────────────────────

def test_list_element_levels_simple():
    levels = fmt.list_element_levels(SIMPLE_XML)
    depths = {lvl["depth"] for lvl in levels}
    assert 0 in depths and 1 in depths and 2 in depths
    # depth 1 should contain "record"
    depth1 = next(lvl for lvl in levels if lvl["depth"] == 1)
    labels = [t["label"] for t in depth1["tags"]]
    assert "record" in labels


def test_list_element_levels_mods_namespace():
    levels = fmt.list_element_levels(MODS_XML)
    depth1 = next(lvl for lvl in levels if lvl["depth"] == 1)
    labels = [t["label"] for t in depth1["tags"]]
    assert "mods:mods" in labels


def test_list_element_levels_clark_tags_present():
    levels = fmt.list_element_levels(MODS_XML)
    depth1 = next(lvl for lvl in levels if lvl["depth"] == 1)
    clark_tags = [t["clark_tag"] for t in depth1["tags"]]
    assert any("loc.gov" in ct for ct in clark_tags)


# ── parse ──────────────────────────────────────────────────────────────────────

def test_parse_direct_children():
    records = list(fmt.parse(SIMPLE_XML))
    assert len(records) == 2
    first = records[0]
    assert "title" in first
    assert first["title"] == "Foto 1"
    assert first["creator"] == "Maier"
    assert "__tree__" in first


def test_parse_second_record_missing_field():
    records = list(fmt.parse(SIMPLE_XML))
    assert "date" not in records[1]  # Foto 2 has no <date>


def test_parse_mods_with_clark_xpath():
    clark_tag = "{http://www.loc.gov/mods/v3}mods"
    records = list(fmt.parse(MODS_XML, record_xpath=clark_tag))
    assert len(records) == 2
    first = records[0]
    # One of the keys should contain "title"
    title_keys = [k for k in first if "title" in k.lower() and k != "__tree__"]
    assert title_keys
    assert "Strassenbahn" in first[title_keys[0]]


def test_parse_flat_no_tree_key():
    records = list(fmt.parse_flat(SIMPLE_XML))
    assert len(records) == 2
    assert "__tree__" not in records[0]
    assert records[0]["title"] == "Foto 1"


def test_parse_dc_namespace():
    records = list(fmt.parse(DC_XML))
    assert len(records) == 2
    first = records[0]
    title_keys = [k for k in first if "title" in k.lower() and k != "__tree__"]
    assert title_keys


# ── list_selectors ─────────────────────────────────────────────────────────────

def test_list_selectors_simple():
    selectors = fmt.list_selectors(SIMPLE_XML)
    paths = [s.path for s in selectors]
    assert "title" in paths
    assert "creator" in paths


def test_list_selectors_have_samples():
    selectors = fmt.list_selectors(SIMPLE_XML)
    title_sel = next(s for s in selectors if s.path == "title")
    assert "Foto 1" in title_sel.sample


def test_list_selectors_mods_readable_labels():
    clark_tag = "{http://www.loc.gov/mods/v3}mods"
    selectors = fmt.list_selectors(MODS_XML, record_xpath=clark_tag)
    labels = [s.label for s in selectors]
    # Labels should use prefix notation, not Clark notation
    assert any("mods:" in lbl for lbl in labels)
    assert not any("{http" in lbl for lbl in labels)


def test_list_selectors_dc_readable_labels():
    selectors = fmt.list_selectors(DC_XML)
    labels = [s.label for s in selectors]
    assert any("dc:title" in lbl or "title" in lbl for lbl in labels)


def test_list_selectors_kind_scalar():
    selectors = fmt.list_selectors(SIMPLE_XML)
    assert all(s.kind == "scalar" for s in selectors)
