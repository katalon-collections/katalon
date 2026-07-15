import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.models import User
from katalon.core.schemas import RefreshTokenRequest, Token
from katalon.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

DBDep = Annotated[AsyncSession, Depends(get_db)]


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(user_id: uuid.UUID, role: str, email: str, token_type: str, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    return jwt.encode(
        {"sub": str(user_id), "role": role, "email": email, "typ": token_type, "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def create_access_token(user_id: uuid.UUID, role: str, email: str) -> str:
    return _create_token(
        user_id,
        role,
        email,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: uuid.UUID, role: str, email: str) -> str:
    return _create_token(
        user_id,
        role,
        email,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def issue_token_pair(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id, user.role, user.email),
        refresh_token=create_refresh_token(user.id, user.role, user.email),
    )


@router.post(
    "/token",
    response_model=Token,
    summary="Authenticate with username/password and issue an access/refresh token pair",
    responses={
        400: {"description": "Account deactivated"},
        401: {"description": "Invalid credentials"},
    },
)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBDep) -> Token:
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültige Anmeldedaten",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Konto deaktiviert")
    return issue_token_pair(user)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Exchange a refresh token for a new access/refresh token pair",
    responses={
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(data: RefreshTokenRequest, db: DBDep) -> Token:
    try:
        payload = jwt.decode(data.refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("typ")
        if user_id_str is None or token_type != "refresh":
            raise ValueError
        user_id = uuid.UUID(user_id_str)
    except (ValueError, JWTError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger Refresh-Token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger Refresh-Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return issue_token_pair(user)
