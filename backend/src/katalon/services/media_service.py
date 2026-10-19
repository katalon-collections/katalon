# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import Object


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
