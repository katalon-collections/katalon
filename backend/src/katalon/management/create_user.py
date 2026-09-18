# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Create a Katalon user from the management CLI."""
from __future__ import annotations

import asyncio

from pydantic import ValidationError


async def _create(email: str, password: str, role: str) -> None:
    from sqlalchemy import select

    from katalon.api.v1.auth import hash_password
    from katalon.core.models import User
    from katalon.core.schemas import UserCreate
    from katalon.database import AsyncSessionLocal

    try:
        data = UserCreate(email=email, password=password, role=role)
    except ValidationError as exc:
        raise ValueError(exc.errors()[0]["msg"]) from exc

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise ValueError("E-Mail bereits vergeben")

        db.add(User(email=data.email, hashed_password=hash_password(data.password), role=data.role))
        await db.commit()


def create_user(email: str, password: str, role: str) -> None:
    """Create a user after validating the shared API input contract."""
    asyncio.run(_create(email=email, password=password, role=role))
