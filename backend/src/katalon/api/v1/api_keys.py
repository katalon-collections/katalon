"""API key management endpoints.

Routes:
  GET    /v1/users/me/api-keys                   – list own keys
  POST   /v1/users/me/api-keys                   – create a new key (key shown once)
  DELETE /v1/users/me/api-keys/{key_id}          – revoke own key
  GET    /v1/users/{user_id}/api-keys            – (admin) list keys for user
  DELETE /v1/users/{user_id}/api-keys/{key_id}  – (admin) revoke key for user
"""

import secrets
import uuid

import bcrypt as _bcrypt
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import ApiKey, User
from katalon.core.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyRead

router = APIRouter(tags=["api-keys"])

_PREFIX = "ktn_"
_KEY_BYTES = 24  # 192 bits → 48 hex chars → total key ≈ 52 chars


def _generate_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, hashed_key)."""
    raw = secrets.token_hex(_KEY_BYTES)
    full_key = f"{_PREFIX}{raw}"
    prefix = full_key[:12]
    hashed = _bcrypt.hashpw(full_key.encode(), _bcrypt.gensalt()).decode()
    return full_key, prefix, hashed


# ---------------------------------------------------------------------------
# Own keys (any authenticated user)
# ---------------------------------------------------------------------------


@router.get("/users/me/api-keys", response_model=list[ApiKeyRead])
async def list_own_api_keys(current_user: CurrentUser, db: DBDep) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id).order_by(ApiKey.created_at)
    )
    return list(result.scalars().all())


@router.post("/users/me/api-keys", response_model=ApiKeyCreated, status_code=201)
async def create_own_api_key(data: ApiKeyCreate, current_user: CurrentUser, db: DBDep) -> ApiKeyCreated:
    full_key, prefix, hashed = _generate_key()
    api_key = ApiKey(
        user_id=current_user.id,
        name=data.name,
        key_prefix=prefix,
        hashed_key=hashed,
        expires_at=data.expires_at,
    )
    db.add(api_key)
    await db.flush()
    return ApiKeyCreated(
        id=api_key.id,
        user_id=api_key.user_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        key=full_key,
    )


@router.delete("/users/me/api-keys/{key_id}", status_code=204)
async def revoke_own_api_key(key_id: uuid.UUID, current_user: CurrentUser, db: DBDep) -> None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API-Schlüssel nicht gefunden")
    await db.delete(api_key)


# ---------------------------------------------------------------------------
# Admin: manage keys for any user
# ---------------------------------------------------------------------------


@router.get("/users/{user_id}/api-keys", response_model=list[ApiKeyRead], dependencies=[require_role("admin")])
async def list_user_api_keys(user_id: uuid.UUID, db: DBDep) -> list[ApiKey]:
    user_result = await db.execute(select(User).where(User.id == user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at)
    )
    return list(result.scalars().all())


@router.post("/users/{user_id}/api-keys", response_model=ApiKeyCreated, status_code=201, dependencies=[require_role("admin")])
async def create_user_api_key(user_id: uuid.UUID, data: ApiKeyCreate, db: DBDep) -> ApiKeyCreated:
    user_result = await db.execute(select(User).where(User.id == user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    full_key, prefix, hashed = _generate_key()
    api_key = ApiKey(
        user_id=user_id,
        name=data.name,
        key_prefix=prefix,
        hashed_key=hashed,
        expires_at=data.expires_at,
    )
    db.add(api_key)
    await db.flush()
    return ApiKeyCreated(
        id=api_key.id,
        user_id=api_key.user_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        key=full_key,
    )


@router.delete("/users/{user_id}/api-keys/{key_id}", status_code=204, dependencies=[require_role("admin")])
async def revoke_user_api_key(user_id: uuid.UUID, key_id: uuid.UUID, db: DBDep) -> None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API-Schlüssel nicht gefunden")
    await db.delete(api_key)
