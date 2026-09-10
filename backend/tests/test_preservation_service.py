# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import hashlib
import io
import uuid
import zipfile
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

from katalon.config import settings
from katalon.services.preservation_service import (
    METS_NS,
    PREMIS_NS,
    BagPayloadEntry,
    MetsFileEntry,
    PremisEvent,
    PremisFile,
    build_bag,
    build_descriptive_xml,
    build_mets,
    build_premis,
)

OBJECT_ID = uuid.uuid4()


def _read_zip(zf: zipfile.ZipFile, name: str) -> str:
    return zf.read(name).decode("utf-8")


def _mets_files() -> list[MetsFileEntry]:
    content = b"fake-image-bytes"
    digest = hashlib.sha256(content).hexdigest()
    return [
        MetsFileEntry(
            file_id="master-1",
            use="master",
            href="../master/abc--scan.tif",
            name="scan.tif",
            mime_type="image/tiff",
            size=len(content),
            checksum=digest,
        ),
        MetsFileEntry(
            file_id="derivatives-1",
            use="derivatives",
            href="../derivatives/abc--scan.tif",
            name="scan.tif",
            mime_type="image/tiff",
            size=len(content),
            checksum=digest,
        ),
    ]


def _events() -> list[PremisEvent]:
    return [
        PremisEvent(
            event_type="creation",
            datetime_utc=datetime(2026, 1, 2, tzinfo=UTC),
            detail="audit action=create; fields: title",
            agent_id=str(uuid.uuid4()),
        ),
        PremisEvent(
            event_type="ingest",
            datetime_utc=datetime(2026, 1, 3, tzinfo=UTC),
            detail="audit action=media_upload",
            agent_id=None,
        ),
    ]


def test_build_bag_structure_and_manifest() -> None:
    payload = [BagPayloadEntry("data/files/master/abc--scan.tif", b"fake-image-bytes")]
    zip_bytes = build_bag(
        external_identifier="OBJ-1",
        descriptive_xml=b"<dc/>",
        mets_xml=b"<mets/>",
        premis_xml=b"<premis/>",
        payload=payload,
    )

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = set(zf.namelist())
    assert "bagit.txt" in names
    assert "bag-info.txt" in names
    assert "manifest-sha256.txt" in names
    assert "data/metadata/descriptive.xml" in names
    assert "data/metadata/mets.xml" in names
    assert "data/metadata/premis.xml" in names
    assert "data/files/master/abc--scan.tif" in names

    bagit = _read_zip(zf, "bagit.txt")
    assert "BagIt-Version: 1.0" in bagit
    assert "Tag-File-Character-Encoding: UTF-8" in bagit

    info = _read_zip(zf, "bag-info.txt")
    assert "External-Identifier: OBJ-1" in info
    # Payload-Oxum covers all 4 data files: payload + dc/mets/premis stubs
    expected_oxum = len(b"fake-image-bytes") + len(b"<dc/>") + len(b"<mets/>") + len(b"<premis/>")
    assert f"Payload-Oxum: {expected_oxum}.4" in info

    manifest = _read_zip(zf, "manifest-sha256.txt")
    expected = hashlib.sha256(b"fake-image-bytes").hexdigest()
    assert f"{expected}  data/files/master/abc--scan.tif" in manifest
    assert "data/metadata/mets.xml" in manifest


def test_build_descriptive_xml_fallback() -> None:
    xml = build_descriptive_xml(object_id=OBJECT_ID, idno="OBJ-1", title="Mein Titel", mapped_element=None)
    root = ET.fromstring(xml)
    dc_ns = "{http://purl.org/dc/elements/1.1/}"
    dc_values = {el.text for el in root.iter() if el.tag == f"{dc_ns}identifier"}
    assert "OBJ-1" in dc_values
    assert f"oai:{settings.oai_repository_domain}:object:{OBJECT_ID}" in dc_values
    titles = [el.text for el in root.iter() if el.tag == f"{dc_ns}title"]
    assert titles == ["Mein Titel"]


def test_build_descriptive_xml_uses_mapped_element() -> None:
    mapped = ET.Element("oai_dc:dc", {"xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/"})
    ET.SubElement(mapped, "dc:title").text = "Mapped"
    xml = build_descriptive_xml(object_id=OBJECT_ID, idno=None, title=None, mapped_element=mapped)
    assert b"Mapped" in xml
    assert f"oai:{settings.oai_repository_domain}".encode() not in xml


def test_build_mets_groups_and_checksums() -> None:
    xml = build_mets(object_id=OBJECT_ID, idno="OBJ-1", files=_mets_files())
    root = ET.fromstring(xml)
    assert root.tag == f"{{{METS_NS}}}mets"
    assert root.get("OBJID") == "OBJ-1"

    grps = {g.get("USE"): g for g in root.iter(f"{{{METS_NS}}}fileGrp")}
    assert set(grps) == {"master", "derivatives"}
    master_files = list(grps["master"].iter(f"{{{METS_NS}}}file"))
    assert len(master_files) == 1
    assert master_files[0].get("CHECKSUMTYPE") == "SHA-256"
    flocat = next(master_files[0].iter(f"{{{METS_NS}}}FLocat"))
    assert flocat.get("{http://www.w3.org/1999/xlink}href") == "../master/abc--scan.tif"

    # structMap references master files only
    fptrs = list(root.iter(f"{{{METS_NS}}}fptr"))
    assert [f.get("FILEID") for f in fptrs] == ["master-1"]


def test_build_premis_events_and_files() -> None:
    digest = hashlib.sha256(b"x").hexdigest()
    files = [PremisFile(name="scan.tif", mime_type="image/tiff", size=1, checksum=digest)]
    xml = build_premis(
        object_id=OBJECT_ID, idno="OBJ-1", title="Titel", events=_events(), files=files
    )
    root = ET.fromstring(xml)
    assert root.tag == f"{{{PREMIS_NS}}}premis"

    event_types = [e.text for e in root.iter(f"{{{PREMIS_NS}}}eventType")]
    assert event_types == ["creation", "ingest"]

    datetimes = [e.text for e in root.iter(f"{{{PREMIS_NS}}}eventDateTime")]
    assert datetimes[0].startswith("2026-01-02")

    details = [e.text for e in root.iter(f"{{{PREMIS_NS}}}eventDetail")]
    assert any("fields: title" in d for d in details)

    # one intellectual entity + one file object
    objects = list(root.iter(f"{{{PREMIS_NS}}}object"))
    assert len(objects) == 2
    assert objects[0].get("{http://www.w3.org/2001/XMLSchema-instance}type") == "premis:intellectualEntity"

    # agent linked only where present
    agents = list(root.iter(f"{{{PREMIS_NS}}}linkingAgentIdentifierValue"))
    assert len(agents) == 1
