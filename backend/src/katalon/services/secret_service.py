from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.models import AppSecret


AI_API_KEY_SECRET = "ai_api_key"


def _fernet() -> Fernet:
    raw_key = settings.katalon_secrets_key.strip()
    if len(raw_key) < 32:
        raise HTTPException(
            status_code=500,
            detail="KATALON_SECRETS_KEY muss gesetzt und mindestens 32 Zeichen lang sein.",
        )
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


async def set_secret(db: AsyncSession, key: str, value: str) -> AppSecret:
    secret = await db.scalar(select(AppSecret).where(AppSecret.key == key))
    encrypted = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    if secret is None:
        secret = AppSecret(key=key, encrypted_value=encrypted)
        db.add(secret)
    else:
        secret.encrypted_value = encrypted
    await db.flush()
    return secret


async def get_secret(db: AsyncSession, key: str) -> str | None:
    secret = await db.scalar(select(AppSecret).where(AppSecret.key == key))
    if secret is None:
        return None
    try:
        return _fernet().decrypt(secret.encrypted_value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise HTTPException(status_code=500, detail="Gespeichertes Secret konnte nicht entschlüsselt werden.") from exc


async def delete_secret(db: AsyncSession, key: str) -> None:
    secret = await db.scalar(select(AppSecret).where(AppSecret.key == key))
    if secret is not None:
        await db.delete(secret)


async def has_secret(db: AsyncSession, key: str) -> bool:
    return await db.scalar(select(AppSecret.key).where(AppSecret.key == key)) is not None
