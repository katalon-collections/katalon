# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Upload and delivery of `file`-field attachments (admin API).

`router` is mounted with the app-wide bearer/API-key dependency. `stream_router`
is mounted without it: the signed link from `/link` is its only credential.
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile

from katalon import config
from katalon.core.dependencies import CurrentUser, DBDep, has_record_permission
from katalon.core.models import Attachment, User
from katalon.services.attachment_service import (
    AttachmentRecordType,
    attachment_file_response,
    build_attachment_link,
    create_attachment,
    load_readable_attachment,
    verify_attachment_link,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])
stream_router = APIRouter(prefix="/attachments", tags=["attachments"])


def _serialize(attachment: Attachment) -> dict[str, Any]:
    return {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
        "size": attachment.size,
    }


# Declared before the `/{attachment_id}/...` GET routes; no path-param route can shadow it.
@router.get(
    "/limits",
    summary="Upload limits for file fields",
    description="Returns {\"max_upload_mb\": n}, the configured maximum upload size.",
)
async def get_attachment_limits(current_user: CurrentUser) -> dict[str, int]:
    return {"max_upload_mb": config.settings.attachment_max_upload_mb}


@router.post(
    "/{record_type}/{record_id}",
    status_code=201,
    summary="Upload an attachment for a record's file field",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Record not found"},
        413: {"description": "File too large"},
        415: {"description": "File content is not an allowed type"},
    },
)
async def upload_attachment(
    record_type: AttachmentRecordType,
    record_id: uuid.UUID,
    file: UploadFile,
    db: DBDep,
    current_user: CurrentUser,
) -> dict[str, Any]:
    if not await has_record_permission(db, current_user, record_type, "update"):
        raise HTTPException(status_code=403, detail="Keine Schreibberechtigung für diesen Datensatztyp.")
    attachment = await create_attachment(
        db,
        record_type=record_type,
        record_id=record_id,
        upload=file,
        created_by=current_user.id,
    )
    return _serialize(attachment)


@router.get(
    "/{attachment_id}/file",
    summary="Serve an attachment file",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Attachment, record or file not found"},
    },
)
async def get_attachment_file(
    attachment_id: uuid.UUID, request: Request, db: DBDep, current_user: CurrentUser
) -> Response:
    attachment = await load_readable_attachment(db, current_user, attachment_id)
    return await attachment_file_response(attachment, request)


@router.get(
    "/{attachment_id}/link",
    summary="Create a short-lived signed stream URL for an attachment",
    description=(
        "Returns {\"url\": path}. The path is relative to the API root and streams the file "
        "without a bearer token (for <video>/<audio>). Valid for 300 seconds, bound to the "
        "attachment and the requesting user; streaming re-checks both."
    ),
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Attachment or record not found"},
    },
)
async def get_attachment_link(
    attachment_id: uuid.UUID, db: DBDep, current_user: CurrentUser
) -> dict[str, str]:
    await load_readable_attachment(db, current_user, attachment_id)
    return {"url": build_attachment_link(attachment_id, current_user.id)}


@stream_router.get(
    "/{attachment_id}/stream",
    summary="Stream an attachment with a signed link (no bearer token)",
    responses={
        403: {"description": "Link invalid, expired, or user no longer allowed"},
        404: {"description": "Attachment, record or file not found"},
    },
)
async def stream_attachment(
    attachment_id: uuid.UUID,
    request: Request,
    db: DBDep,
    uid: str | None = None,
    exp: str | None = None,
    sig: str | None = None,
) -> Response:
    user_id = verify_attachment_link(attachment_id, uid, exp, sig)
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="Link ungültig oder abgelaufen")
    attachment = await load_readable_attachment(db, user, attachment_id)
    return await attachment_file_response(attachment, request)
