import uuid
from datetime import datetime
from typing import Annotated

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.models import ApiKey, User
from katalon.core.schemas import TokenData
from katalon.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

DBDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    api_key: Annotated[str | None, Security(api_key_header)],
    db: DBDep,
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # --- Try API key first if provided ---
    if api_key:
        if not api_key.startswith("ktn_"):
            raise credentials_exception
        prefix = api_key[:12]
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True))
        )
        candidates = result.scalars().all()
        matched: ApiKey | None = None
        for candidate in candidates:
            if _bcrypt.checkpw(api_key.encode(), candidate.hashed_key.encode()):
                matched = candidate
                break
        if matched is None:
            raise credentials_exception
        if matched.expires_at is not None:
            if datetime.utcnow() > matched.expires_at:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API-Schlüssel abgelaufen")
        matched.last_used_at = datetime.utcnow()
        user_result = await db.execute(select(User).where(User.id == matched.user_id))
        user = user_result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise credentials_exception
        return user

    # --- Fall back to JWT Bearer token ---
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_str: str | None = payload.get("sub")
        role: str | None = payload.get("role")
        if user_id_str is None or role is None:
            raise credentials_exception
        token_data = TokenData(user_id=uuid.UUID(user_id_str), role=role)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def try_get_current_user(request: Request, db: DBDep) -> User | None:
    """Like get_current_user but returns None instead of raising 401.

    Checks X-API-Key header first, then falls back to JWT Bearer.
    """
    # Check X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key and api_key.startswith("ktn_"):
        prefix = api_key[:12]
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True))
        )
        for candidate in result.scalars().all():
            if _bcrypt.checkpw(api_key.encode(), candidate.hashed_key.encode()):
                if candidate.expires_at and datetime.utcnow() > candidate.expires_at:
                    return None
                candidate.last_used_at = datetime.utcnow()
                user_result = await db.execute(select(User).where(User.id == candidate.user_id))
                user = user_result.scalar_one_or_none()
                return user if user and user.is_active else None
        return None

    # Check JWT Bearer
    authorization = request.headers.get("Authorization", "")
    scheme, token = get_authorization_scheme_param(authorization)
    if not token or scheme.lower() != "bearer":
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            return None
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id_str)))
        user = result.scalar_one_or_none()
        return user if user and user.is_active else None
    except (JWTError, ValueError):
        return None


OptionalCurrentUser = Annotated[User | None, Depends(try_get_current_user)]


def require_role(*roles: str):
    async def _check(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return Depends(_check)


def require_admin_or_editor():
    """Allow admin, editor, and cataloger for content operations."""
    return require_role("admin", "editor", "cataloger")


def require_admin():
    return require_role("admin")
