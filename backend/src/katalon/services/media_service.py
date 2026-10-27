# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import MediaFile, Object


async def touch_object(session: AsyncSession, object_id: uuid.UUID) -> None:
    """Move the object's ``updated_at`` after a change to its media.

    Public media are part of the object's export (LIDO resourceSet, METS file
    section), and ``updated_at`` is the OAI-PMH datestamp and LIDO
    ``recordMetadataDate``. Without this, incremental harvests (``from=``) miss
    media-only changes. The caller commits and reindexes.
    """
    obj = await session.get(Object, object_id)
    if obj is not None:
        obj.updated_at = datetime.now(UTC).replace(tzinfo=None)


async def primary_media_files_by_object(
    session: AsyncSession, object_ids: list[uuid.UUID], *, public_only: bool
) -> dict[uuid.UUID, MediaFile]:
    """Preview file per object as portal teasers show it: the ready primary file, otherwise
    the oldest ready one. One query for all objects; visibility of the objects themselves
    is the caller's job."""
    query = select(MediaFile).where(
        MediaFile.object_id.in_(object_ids),
        MediaFile.deleted_at.is_(None),
        MediaFile.status == "ready",
    )
    if public_only:
        query = query.where(MediaFile.is_public.is_(True))
    result = await session.execute(query.order_by(MediaFile.is_primary.desc(), MediaFile.created_at))
    primary: dict[uuid.UUID, MediaFile] = {}
    for f in result.scalars().all():
        primary.setdefault(f.object_id, f)
    return primary
