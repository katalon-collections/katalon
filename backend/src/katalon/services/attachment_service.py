# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Dateianhänge am Feldtyp "file": Upload, Inhaltsprüfung, Auslieferung, signierte Links."""

import asyncio
import hashlib
import hmac
import json
import logging
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlencode

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon import config
from katalon.core.dependencies import has_record_permission
from katalon.core.media_storage import (
    LocalStorage,
    S3Storage,
    attachment_storage_key,
    get_storage,
)
from katalon.core.media_validation import ALLOWED_ATTACHMENT_MIME, sniff_media_mime
from katalon.core.models import (
    Attachment,
    Collection,
    Entity,
    Object,
    Occurrence,
    Place,
    Procedure,
    RecordSnapshot,
    StorageLocation,
    User,
)

logger = logging.getLogger(__name__)

# Record types that may carry a `file` field. Vocabulary terms are excluded on purpose.
ATTACHMENT_RECORD_MODELS: dict[str, Any] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "procedure": Procedure,
    "collection": Collection,
    "storage_location": StorageLocation,
}
# Internal types: never served through the portal.
INTERNAL_ATTACHMENT_RECORD_TYPES = frozenset({"procedure", "storage_location"})
ATTACHMENT_RECORD_TYPES = frozenset(ATTACHMENT_RECORD_MODELS)
AttachmentRecordType = Literal[
    "object", "entity", "place", "occurrence", "procedure", "collection", "storage_location"
]

ATTACHMENT_LINK_TTL_SECONDS = 300
_CHUNK_SIZE = 1024 * 1024
_CSP_SANDBOX = "default-src 'none'; sandbox"
# PDF viewers in browsers do not render under the sandbox directive.
# The browser PDF viewer is plugin content: it needs object-src for the file itself.
_CSP_PDF = "default-src 'none'; object-src 'self'; frame-ancestors 'self'"


async def load_attachment_record(db: AsyncSession, record_type: str, record_id: uuid.UUID) -> Any:
    """Return the owning record; 404 when it is missing or soft-deleted."""
    model = ATTACHMENT_RECORD_MODELS[record_type]
    query = select(model).where(model.id == record_id)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    record = (await db.execute(query)).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Datensatz nicht gefunden")
    return record


def _as_uuid(value: object) -> uuid.UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _file_refs(label: str, value: object, repeatable: bool) -> list[tuple[str, dict[str, Any]]]:
    """(label, value dict) for each well-formed file reference in one field value."""
    items = value if repeatable else [value]
    if not isinstance(items, list):
        return []
    return [
        (label, item)
        for item in items
        if isinstance(item, dict) and _as_uuid(item.get("id")) is not None
    ]


async def check_and_normalize_attachment_refs(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID | None,
    metadata: dict[str, Any],
    field_defs: list[Any],
) -> list[str]:
    """Trust boundary for `file` values on save.

    Every referenced attachment must belong to (record_type, record_id). Each
    referenced value is then rewritten in place to the stored id, filename,
    mime_type and size, so client-supplied keys never reach the metadata.
    `field_defs` are the top-level definitions; group sub-fields are read here.
    Structurally malformed values are left to schema_service.
    """
    from katalon.services.schema_service import get_sub_field_definitions

    refs: list[tuple[str, dict[str, Any]]] = []
    for field in field_defs:
        if field.field_type == "file":
            refs.extend(_file_refs(field.name, metadata.get(field.name), field.is_repeatable))
        elif field.field_type == "group":
            instances = metadata.get(field.name)
            if not isinstance(instances, list):
                continue
            file_subs = [
                sf
                for sf in await get_sub_field_definitions(db, field.id)
                if sf.field_type == "file"
            ]
            for idx, instance in enumerate(instances):
                if not isinstance(instance, dict):
                    continue
                for sf in file_subs:
                    label = f"{field.name}.{sf.name} (Eintrag {idx + 1})"
                    refs.extend(_file_refs(label, instance.get(sf.name), sf.is_repeatable))
    if not refs:
        return []

    if record_id is None:
        labels = dict.fromkeys(label for label, _ in refs)
        return [
            f"Feld '{label}': Dateien können erst nach dem Speichern des Datensatzes hochgeladen werden."
            for label in labels
        ]

    ids = {_as_uuid(item["id"]) for _, item in refs}
    rows = (
        (
            await db.execute(
                select(Attachment).where(
                    Attachment.id.in_(ids),
                    Attachment.record_type == record_type,
                    Attachment.record_id == record_id,
                )
            )
        )
        .scalars()
        .all()
    )
    by_id = {row.id: row for row in rows}

    errors = list(
        dict.fromkeys(
            f"Feld '{label}': Datei gehört nicht zu diesem Datensatz."
            for label, item in refs
            if _as_uuid(item["id"]) not in by_id
        )
    )
    if errors:
        return errors

    pairs = [(item, by_id[_as_uuid(item["id"])]) for _, item in refs]
    for item, row in pairs:
        item.clear()
        item.update(
            {"id": str(row.id), "filename": row.filename, "mime_type": row.mime_type, "size": row.size}
        )
    return []


async def purge_record_attachments(db: AsyncSession, record_type: str, record_id: uuid.UUID) -> None:
    """Hard delete: drop the record's attachment rows and their stored files.

    A storage failure is logged and does not block the database deletion, as for
    page assets. Files that could not be removed stay on disk without a row;
    `katalon-manage attachments-gc` does not find them.
    """
    rows = (
        (
            await db.execute(
                select(Attachment).where(
                    Attachment.record_type == record_type, Attachment.record_id == record_id
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return
    try:
        await get_storage().delete(*[row.storage_key for row in rows])
    except Exception:
        logger.warning(
            "Physisches Löschen der Anhänge von %s %s fehlgeschlagen",
            record_type,
            record_id,
            exc_info=True,
        )
    for row in rows:
        await db.delete(row)


def parse_older_than(value: str) -> timedelta:
    """Parse the GC age: "<n>d", "<n>h" or "0" (everything, regardless of age)."""
    text = value.strip().lower()
    if text == "0":
        return timedelta(0)
    if len(text) >= 2 and text[:-1].isdigit() and text[-1] in ("d", "h"):
        amount = int(text[:-1])
        return timedelta(days=amount) if text[-1] == "d" else timedelta(hours=amount)
    raise ValueError(f"Ungültige Frist '{value}': erwartet '<n>d', '<n>h' oder '0'.")


async def gc_attachments(
    db: AsyncSession, *, older_than: timedelta, dry_run: bool
) -> dict[str, int]:
    """Delete old attachment rows and files that no current or snapshot metadata references.

    A row is kept while its id occurs in the owning record's metadata (trashed
    records included) or in any snapshot of that record. A missing owner means
    the row is an orphan. Storage failures keep the row so the next run retries.
    """
    cutoff = datetime.now(UTC).replace(tzinfo=None) - older_than
    candidates = (
        (await db.execute(select(Attachment).where(Attachment.created_at < cutoff))).scalars().all()
    )
    report = {"candidates": len(candidates), "referenced": 0, "orphaned": 0, "deleted": 0, "failed": 0}

    grouped: dict[tuple[str, uuid.UUID], list[Attachment]] = {}
    for row in candidates:
        grouped.setdefault((row.record_type, row.record_id), []).append(row)

    to_delete: list[Attachment] = []
    for (record_type, record_id), rows in grouped.items():
        model = ATTACHMENT_RECORD_MODELS.get(record_type)
        owner = None
        if model is not None:
            owner = (
                await db.execute(select(model.metadata_).where(model.id == record_id))
            ).first()
        owner_exists = owner is not None
        texts: list[str] = []
        if owner is not None:
            texts.append(json.dumps(owner[0] or {}, default=str))
            snapshots = (
                await db.execute(
                    select(RecordSnapshot.snapshot).where(
                        RecordSnapshot.record_type == record_type,
                        RecordSnapshot.record_id == record_id,
                    )
                )
            ).scalars().all()
            texts.extend(json.dumps(snap, default=str) for snap in snapshots)
        for row in rows:
            if not owner_exists:
                report["orphaned"] += 1
                to_delete.append(row)
            elif any(str(row.id) in text for text in texts):
                report["referenced"] += 1
            else:
                to_delete.append(row)

    if dry_run:
        report["deleted"] = len(to_delete)
        return report

    for row in to_delete:
        try:
            await get_storage().delete(row.storage_key)
        except Exception as exc:
            # Keep the row when its file could not be removed, so the next run retries.
            report["failed"] += 1
            logger.warning("Anhang %s konnte nicht gelöscht werden: %s", row.id, exc)
            continue
        await db.delete(row)
        report["deleted"] += 1
    await db.commit()
    return report


async def stream_upload_to_temp(upload: UploadFile, max_bytes: int) -> tuple[Path, int]:
    """Copy the upload into a temporary file; abort with 413 as soon as max_bytes is exceeded.

    The caller owns the returned file and must unlink it.
    """
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        path = Path(tmp.name)
        size = 0
        try:
            while chunk := await upload.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Datei zu groß (maximal {max_bytes // (1024 * 1024)} MB)",
                    )
                tmp.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    return path, size


def verify_attachment_content(path: Path) -> str:
    """Return the content-detected MIME type; 415 for anything outside PDF, image, audio, video."""
    mime_type = sniff_media_mime(path)
    if mime_type is None or mime_type not in ALLOWED_ATTACHMENT_MIME:
        raise HTTPException(
            status_code=415,
            detail="Dateityp nicht erlaubt. Erlaubt sind PDF, Bild, Audio und Video.",
        )
    return mime_type


async def create_attachment(
    db: AsyncSession,
    *,
    record_type: str,
    record_id: uuid.UUID,
    upload: UploadFile,
    created_by: uuid.UUID,
) -> Attachment:
    """Store an upload and add its `attachments` row. The metadata reference is written on save."""
    await load_attachment_record(db, record_type, record_id)
    max_bytes = config.settings.attachment_max_upload_mb * 1024 * 1024
    tmp_path, size = await stream_upload_to_temp(upload, max_bytes)
    try:
        mime_type = verify_attachment_content(tmp_path)
        attachment_id = uuid.uuid4()
        filename = (Path(upload.filename or "").name or "upload")[:512]
        key = attachment_storage_key(attachment_id, filename)
        await get_storage().put_file(key, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    attachment = Attachment(
        id=attachment_id,
        record_type=record_type,
        record_id=record_id,
        filename=filename,
        mime_type=mime_type,
        size=size,
        storage_key=key,
        created_by=created_by,
    )
    db.add(attachment)
    await db.flush()
    return attachment


async def load_readable_attachment(
    db: AsyncSession, user: User, attachment_id: uuid.UUID
) -> Attachment:
    """Attachment the user may read: read permission on its record type, record still present."""
    attachment = await db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
    if not await has_record_permission(db, user, attachment.record_type, "read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    await load_attachment_record(db, attachment.record_type, attachment.record_id)
    return attachment


LinkScope = Literal["attachment", "media"]


def _link_signature(
    resource_id: uuid.UUID, user_id: uuid.UUID, expires_at: int, scope: LinkScope = "attachment"
) -> str:
    # The scope is part of the signed message, so a link issued for one file kind
    # never verifies for another, even when the resource ids would match.
    key = hmac.new(config.settings.secret_key.encode(), b"attachment-link", hashlib.sha256).digest()
    message = f"{scope}:{resource_id}:{user_id}:{expires_at}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def build_signed_query(
    resource_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    scope: LinkScope = "attachment",
    now: float | None = None,
) -> str:
    """Return the `exp`, `uid`, `sig` query string of a signed stream link."""
    expires_at = int((time.time() if now is None else now) + ATTACHMENT_LINK_TTL_SECONDS)
    return urlencode(
        {
            "exp": expires_at,
            "uid": str(user_id),
            "sig": _link_signature(resource_id, user_id, expires_at, scope),
        }
    )


def verify_signed_link(
    resource_id: uuid.UUID,
    uid: str | None,
    exp: str | None,
    sig: str | None,
    *,
    scope: LinkScope = "attachment",
) -> uuid.UUID:
    """Return the user id a valid, unexpired link of this scope was issued to; 403 otherwise."""
    forbidden = HTTPException(status_code=403, detail="Link ungültig oder abgelaufen")
    if not uid or not exp or not sig:
        raise forbidden
    try:
        expires_at = int(exp)
        user_id = uuid.UUID(uid)
    except ValueError:
        raise forbidden from None
    if expires_at < time.time():
        raise forbidden
    expected = _link_signature(resource_id, user_id, expires_at, scope)
    if not hmac.compare_digest(expected.encode(), sig.encode()):
        raise forbidden
    return user_id


def build_attachment_link(
    attachment_id: uuid.UUID, user_id: uuid.UUID, *, now: float | None = None
) -> str:
    """Return a path below the API root that streams the file without a bearer token.

    The link is an HMAC over attachment id, user id and expiry, valid for
    ATTACHMENT_LINK_TTL_SECONDS. Streaming re-checks the user and the read permission.
    """
    query = build_signed_query(attachment_id, user_id, scope="attachment", now=now)
    return f"/v1/attachments/{attachment_id}/stream?{query}"


def verify_attachment_link(
    attachment_id: uuid.UUID, uid: str | None, exp: str | None, sig: str | None
) -> uuid.UUID:
    """Return the user id a valid, unexpired link was issued to; 403 otherwise."""
    return verify_signed_link(attachment_id, uid, exp, sig, scope="attachment")


def _single_byte_range(header: str, size: int) -> tuple[int, int] | None:
    """Parse one `bytes=` range into inclusive (start, end).

    None means the header is ignored and the full body is sent. Unsatisfiable
    ranges raise 416.
    """
    unit, _, spec = header.partition("=")
    if unit.strip().lower() != "bytes" or "," in spec:
        return None
    first, _, last = spec.strip().partition("-")
    try:
        if first == "":
            length = int(last)
            if length <= 0:
                raise HTTPException(
                    status_code=416, headers={"Content-Range": f"bytes */{size}"}
                )
            start, end = max(size - length, 0), size - 1
        else:
            start = int(first)
            end = int(last) if last else size - 1
    except ValueError:
        return None
    if size == 0 or start >= size:
        raise HTTPException(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    end = min(end, size - 1)
    if end < start:
        return None
    return start, end


def _content_disposition(filename: str) -> str:
    """Inline disposition; non-ASCII or unsafe names use RFC 5987 filename*."""
    encoded = quote(filename)
    if encoded != filename:
        return f"inline; filename*=utf-8''{encoded}"
    return f'inline; filename="{filename}"'


def file_security_headers(mime_type: str) -> dict[str, str]:
    """Headers every stored file response carries, for attachments and media alike.

    The API sets the CSP itself, per content type: the outer nginx keeps its page CSP
    off these responses, so this is the only CSP a browser sees for the file.
    """
    csp = _CSP_PDF if mime_type == "application/pdf" else _CSP_SANDBOX
    return {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": csp}


async def attachment_file_response(attachment: Attachment, request: Request) -> Response:
    """Serve an attachment inline with a strict content type and Range support.

    Local storage uses FileResponse (Range handled by Starlette); S3 streams the
    requested byte range from the bucket. Callers check permissions first.
    """
    storage = get_storage()
    headers: dict[str, str] = {
        **file_security_headers(attachment.mime_type),
        "Cache-Control": "private, no-store",
        "Accept-Ranges": "bytes",
    }
    if isinstance(storage, LocalStorage):
        path = storage.local_path(attachment.storage_key)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Datei nicht gefunden")
        return FileResponse(
            path,
            media_type=attachment.mime_type,
            filename=attachment.filename,
            content_disposition_type="inline",
            headers=headers,
        )

    assert isinstance(storage, S3Storage)
    key = attachment.storage_key
    try:
        size = await asyncio.to_thread(storage.size, key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden") from None
    headers["Content-Disposition"] = _content_disposition(attachment.filename)
    range_header = request.headers.get("range")
    byte_range = _single_byte_range(range_header, size) if range_header else None
    if byte_range is None:
        return StreamingResponse(
            storage.stream(key),
            media_type=attachment.mime_type,
            headers={**headers, "Content-Length": str(size)},
        )
    start, end = byte_range
    return StreamingResponse(
        storage.stream_range(key, start, end),
        status_code=206,
        media_type=attachment.mime_type,
        headers={
            **headers,
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(end - start + 1),
        },
    )
