# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""BagIt/METS/PREMIS preservation package export (POC).

Builds one preservation bag per Object, triggered manually, delivered as a ZIP
download. Structure per `almanac/decisions/preservation/bagit-preservation-export.md`:

    bag/
    ├── bagit.txt
    ├── manifest-sha256.txt
    ├── bag-info.txt
    └── data/
        ├── metadata/
        │   ├── mets.xml
        │   ├── premis.xml
        │   └── descriptive.xml
        └── files/
            ├── master/...
            └── derivatives/...

The bag assembly is deliberately transport-agnostic (pure bytes in/out) so that
later increments — destination adapters (SFTP/S3/HTTP PUT) and batch Celery
jobs — can reuse `build_bag` unchanged.
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.media_storage import get_storage, pyramid_storage_key, safe_filename
from katalon.core.models import AuditLog, MediaFile, Object
from katalon.integrations.oai_dc_format import DC_NS, OaiDcFormat
from katalon.services import export_context_service, metadata_mapping_service
from katalon.services.search_service import _extract_title

logger = logging.getLogger(__name__)

BAGIT_VERSION = "1.0"
SOFTWARE_AGENT = "Katalon Preservation Export (POC)"
METS_NS = "http://www.loc.gov/METS/"
XLINK_NS = "http://www.w3.org/1999/xlink"
PREMIS_NS = "http://www.loc.gov/premis/v3"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

# PREMIS eventType mapping from audit-log actions
_PREMIS_EVENT_TYPES: dict[str, str] = {
    "create": "creation",
    "update": "modification",
    "delete": "deletion",
    "publish": "publication",
    "media_upload": "ingest",
    "media_import": "ingest",
}


class PreservationExportError(Exception):
    """Raised when a preservation package cannot be built."""


@dataclass(frozen=True)
class BagPayloadEntry:
    """One file inside the bag's data/ directory."""

    bag_path: str  # relative to bag root, always starts with "data/"
    content: bytes


@dataclass(frozen=True)
class MetsFileEntry:
    file_id: str
    use: str  # "master" | "derivatives"
    href: str  # relative to data/metadata/mets.xml
    name: str
    mime_type: str
    size: int
    checksum: str


@dataclass(frozen=True)
class PremisEvent:
    event_type: str
    datetime_utc: datetime
    detail: str
    agent_id: str | None


@dataclass(frozen=True)
class PremisFile:
    name: str
    mime_type: str
    size: int
    checksum: str


# ---------------------------------------------------------------------------
# XML builders (pure)
# ---------------------------------------------------------------------------


def build_descriptive_xml(
    *,
    object_id: uuid.UUID,
    idno: str | None,
    title: str | None,
    mapped_element: ET.Element | None,
) -> bytes:
    """Serialize descriptive metadata (Dublin Core) for data/metadata/descriptive.xml.

    Uses the rendered oai_dc element when a published mapping exists, otherwise
    falls back to a minimal record (identifier + title).
    """
    if mapped_element is not None:
        xml: bytes = ET.tostring(mapped_element, encoding="UTF-8", xml_declaration=True)
        return xml

    dc = ET.Element("oai_dc:dc", {
        "xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "xmlns:dc": DC_NS,
        "xmlns:xsi": XSI_NS,
        "xsi:schemaLocation": (
            "http://www.openarchives.org/OAI/2.0/oai_dc/ "
            "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
        ),
    })
    if title:
        ET.SubElement(dc, "dc:title").text = title
    ET.SubElement(dc, "dc:identifier").text = f"oai:{settings.oai_repository_domain}:object:{object_id}"
    if idno:
        ET.SubElement(dc, "dc:identifier").text = idno
    ET.SubElement(dc, "dc:type").text = "object"
    fallback: bytes = ET.tostring(dc, encoding="UTF-8", xml_declaration=True)
    return fallback


def build_mets(
    *,
    object_id: uuid.UUID,
    idno: str | None,
    files: list[MetsFileEntry],
) -> bytes:
    """Build minimal METS structural metadata (master vs. derivative file groups)."""
    mets = ET.Element("mets:mets", {
        "xmlns:mets": METS_NS,
        "xmlns:xlink": XLINK_NS,
        "OBJID": idno or str(object_id),
        "TYPE": "object",
    })

    ET.SubElement(
        ET.SubElement(mets, "mets:dmdSec", {"ID": "dmd-descriptive"}),
        "mets:mdRef",
        {"MDTYPE": "DC", "LOCTYPE": "URL", "xlink:href": "descriptive.xml"},
    )

    file_sec = ET.SubElement(mets, "mets:fileSec")
    for use in ("master", "derivatives"):
        grp = ET.SubElement(file_sec, "mets:fileGrp", {"USE": use})
        for f in files:
            if f.use != use:
                continue
            file_el = ET.SubElement(grp, "mets:file", {
                "ID": f.file_id,
                "MIMETYPE": f.mime_type,
                "SIZE": str(f.size),
                "CHECKSUM": f.checksum,
                "CHECKSUMTYPE": "SHA-256",
            })
            ET.SubElement(file_el, "mets:FLocat", {
                "LOCTYPE": "URL",
                "xlink:href": f.href,
                "xlink:title": f.name,
            })

    struct_map = ET.SubElement(mets, "mets:structMap")
    div = ET.SubElement(struct_map, "mets:div", {"TYPE": "object", "DMDID": "dmd-descriptive"})
    for f in files:
        if f.use == "master":
            ET.SubElement(div, "mets:fptr", {"FILEID": f.file_id})

    xml: bytes = ET.tostring(mets, encoding="UTF-8", xml_declaration=True)
    return xml


def build_premis(
    *,
    object_id: uuid.UUID,
    idno: str | None,
    title: str | None,
    events: list[PremisEvent],
    files: list[PremisFile],
) -> bytes:
    """Build minimal PREMIS record: one intellectual-entity object, file objects, events."""
    premis = ET.Element("premis:premis", {
        "xmlns:premis": PREMIS_NS,
        "xmlns:xsi": XSI_NS,
        "version": "3.0",
    })

    ie = ET.SubElement(premis, "premis:object", {"xsi:type": "premis:intellectualEntity"})
    ident = ET.SubElement(ie, "premis:objectIdentifier")
    ET.SubElement(ident, "premis:objectIdentifierType").text = "UUID"
    ET.SubElement(ident, "premis:objectIdentifierValue").text = str(object_id)
    ET.SubElement(ie, "premis:originalName").text = title or idno or str(object_id)

    for f in files:
        obj = ET.SubElement(premis, "premis:object", {"xsi:type": "premis:file"})
        ident = ET.SubElement(obj, "premis:objectIdentifier")
        ET.SubElement(ident, "premis:objectIdentifierType").text = "local"
        ET.SubElement(ident, "premis:objectIdentifierValue").text = f.name
        ch = ET.SubElement(obj, "premis:objectCharacteristics")
        ET.SubElement(ch, "premis:format").text = f.mime_type
        ET.SubElement(ch, "premis:size").text = str(f.size)
        fix = ET.SubElement(ch, "premis:fixity")
        ET.SubElement(fix, "premis:messageDigestAlgorithm").text = "SHA-256"
        ET.SubElement(fix, "premis:messageDigest").text = f.checksum

    for i, ev in enumerate(events, start=1):
        event = ET.SubElement(premis, "premis:event")
        ident = ET.SubElement(event, "premis:eventIdentifier")
        ET.SubElement(ident, "premis:eventIdentifierType").text = "local"
        ET.SubElement(ident, "premis:eventIdentifierValue").text = f"audit-{i}"
        ET.SubElement(event, "premis:eventType").text = ev.event_type
        ET.SubElement(event, "premis:eventDateTime").text = ev.datetime_utc.isoformat()
        detail = ET.SubElement(event, "premis:eventDetailInformation")
        ET.SubElement(detail, "premis:eventDetail").text = ev.detail
        if ev.agent_id:
            agent = ET.SubElement(event, "premis:linkingAgentIdentifier")
            ET.SubElement(agent, "premis:linkingAgentIdentifierType").text = "local"
            ET.SubElement(agent, "premis:linkingAgentIdentifierValue").text = ev.agent_id

    xml: bytes = ET.tostring(premis, encoding="UTF-8", xml_declaration=True)
    return xml


# ---------------------------------------------------------------------------
# Bag assembly (pure)
# ---------------------------------------------------------------------------


def build_bag(
    *,
    external_identifier: str,
    descriptive_xml: bytes,
    mets_xml: bytes,
    premis_xml: bytes,
    payload: list[BagPayloadEntry],
) -> bytes:
    """Assemble a complete BagIt bag and return it as ZIP bytes (bag at zip root).

    Implements RFC 8493 with SHA-256 manifests. The payload list covers all
    data/ files except the three metadata documents, which are added here.
    """
    data_files = [
        BagPayloadEntry("data/metadata/descriptive.xml", descriptive_xml),
        BagPayloadEntry("data/metadata/mets.xml", mets_xml),
        BagPayloadEntry("data/metadata/premis.xml", premis_xml),
        *payload,
    ]

    manifest_lines = []
    total_bytes = 0
    for entry in data_files:
        digest = hashlib.sha256(entry.content).hexdigest()
        manifest_lines.append(f"{digest}  {entry.bag_path}")
        total_bytes += len(entry.content)

    bagit_txt = f"BagIt-Version: {BAGIT_VERSION}\nTag-File-Character-Encoding: UTF-8\n"
    bag_info = (
        f"Bag-Software-Agent: {SOFTWARE_AGENT}\n"
        f"Bagging-Date: {datetime.now(UTC).date().isoformat()}\n"
        f"Payload-Oxum: {total_bytes}.{len(data_files)}\n"
        f"External-Identifier: {external_identifier}\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bagit.txt", bagit_txt)
        zf.writestr("bag-info.txt", bag_info)
        zf.writestr("manifest-sha256.txt", "\n".join(manifest_lines) + "\n")
        for entry in data_files:
            zf.writestr(entry.bag_path, entry.content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Orchestration (DB-bound)
# ---------------------------------------------------------------------------


def _audit_event(entry: AuditLog) -> PremisEvent:
    action = entry.action
    event_type = _PREMIS_EVENT_TYPES.get(action)
    if event_type is None:
        event_type = "ingest" if action.startswith("media_") else "modification"
    fields = sorted((dict(entry.changed_fields or {})).keys())
    detail = f"audit action={action}"
    if fields:
        detail += f"; fields: {', '.join(fields)}"
    return PremisEvent(
        event_type=event_type,
        datetime_utc=entry.created_at,
        detail=detail,
        agent_id=str(entry.user_id) if entry.user_id else None,
    )


async def _render_oai_dc(db: AsyncSession, object_id: uuid.UUID) -> ET.Element | None:
    """Render the Object through the published oai_dc mapping, or None if unmapped."""
    index = await metadata_mapping_service.get_mapping_index(db, "oai_dc")
    mapping = index.get("object")
    if not mapping or not mapping.rules:
        return None
    ctx = await export_context_service.build_export_context_from_db(db, "object", object_id)
    return OaiDcFormat().render(ctx, mapping)


async def build_object_preservation_zip(db: AsyncSession, object_id: uuid.UUID) -> tuple[str, bytes]:
    """Build a preservation bag ZIP for one Object. Returns (filename, zip bytes)."""
    obj = await db.get(Object, object_id)
    if not obj or obj.deleted_at is not None:
        raise PreservationExportError(f"Objekt {object_id} nicht gefunden.")

    result = await db.execute(
        select(MediaFile)
        .where(MediaFile.object_id == object_id, MediaFile.status != "error")
        .order_by(MediaFile.is_primary.desc(), MediaFile.created_at)
    )
    media_files = list(result.scalars().all())

    # Payload: masters + pyramid derivatives, read from managed local storage
    payload: list[BagPayloadEntry] = []
    mets_files: list[MetsFileEntry] = []
    premis_files: list[PremisFile] = []

    def add_file(bag_path: str, content: bytes, mime_type: str, use: str, name: str) -> None:
        digest = hashlib.sha256(content).hexdigest()
        payload.append(BagPayloadEntry(bag_path, content))
        mets_files.append(MetsFileEntry(
            file_id=f"{use}-{len(mets_files) + 1}",
            use=use,
            href=f"../{bag_path.removeprefix('data/files/')}",
            name=name,
            mime_type=mime_type,
            size=len(content),
            checksum=digest,
        ))
        premis_files.append(PremisFile(name=name, mime_type=mime_type, size=len(content), checksum=digest))

    for mf in media_files:
        master_path = f"data/files/master/{mf.id}--{safe_filename(mf.filename)}"
        try:
            content = await get_storage().read_bytes(mf.storage_key)
        except FileNotFoundError:
            logger.warning("Preservation export: media file %s missing on disk, skipped", mf.id)
            continue
        add_file(master_path, content, mf.mime_type, "master", mf.filename)

        if mf.iiif_storage_key:
            derivative_path = f"data/files/derivatives/{mf.id}--{safe_filename(mf.filename)}"
            try:
                derivative = await get_storage().read_bytes(pyramid_storage_key(mf.storage_key))
            except FileNotFoundError:
                logger.warning(
                    "Preservation export: pyramid derivative for media %s missing, skipped", mf.id
                )
                continue
            add_file(derivative_path, derivative, "image/tiff", "derivatives", mf.filename)

    # PREMIS events from audit log
    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.record_type == "object", AuditLog.record_id == object_id)
        .order_by(AuditLog.created_at)
    )
    events: list[PremisEvent] = []
    for entry in audit_result.scalars().all():
        events.append(_audit_event(entry))

    title = _extract_title(obj.metadata_ or {}) or obj.idno
    mapped = await _render_oai_dc(db, object_id)
    descriptive_xml = build_descriptive_xml(
        object_id=object_id, idno=obj.idno, title=str(title) if title else None, mapped_element=mapped
    )
    mets_xml = build_mets(object_id=object_id, idno=obj.idno, files=mets_files)
    premis_xml = build_premis(
        object_id=object_id, idno=obj.idno, title=str(title) if title else None,
        events=events, files=premis_files,
    )

    zip_content = build_bag(
        external_identifier=obj.idno or str(object_id),
        descriptive_xml=descriptive_xml,
        mets_xml=mets_xml,
        premis_xml=premis_xml,
        payload=payload,
    )
    filename = f"preservation-{safe_filename(obj.idno or str(object_id))}.zip"
    return filename, zip_content
