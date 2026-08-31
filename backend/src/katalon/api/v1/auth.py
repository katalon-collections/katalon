import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.limiter import limiter
from katalon.core.models import PasswordResetToken, User
from katalon.core.schemas import (
    PasswordResetConfirm,
    PasswordResetRequest,
    Token,
)
from katalon.database import get_db
from katalon.services.secret_service import encrypt_value
from katalon.workers.email_tasks import send_password_reset_email
from katalon.workers.enqueue import enqueue

router = APIRouter(prefix="/auth", tags=["auth"])

DBDep = Annotated[AsyncSession, Depends(get_db)]
REFRESH_COOKIE = "katalon_refresh_token"
REFRESH_COOKIE_PATH = "/v1/"


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(
    user_id: uuid.UUID, role: str, email: str, token_type: str, expires_delta: timedelta, token_version: int
) -> str:
    expire = datetime.now(UTC) + expires_delta
    return cast(
        str,
        jwt.encode(
            {"sub": str(user_id), "role": role, "email": email, "typ": token_type, "ver": token_version, "exp": expire},
            settings.secret_key,
            algorithm=settings.algorithm,
        ),
    )


def create_access_token(user: User) -> str:
    return _create_token(
        user.id,
        user.role,
        user.email,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes), user.token_version,
    )


def create_refresh_token(user: User) -> str:
    return _create_token(
        user.id,
        user.role,
        user.email,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days), user.token_version,
    )


def issue_token_pair(user: User, response: Response) -> Token:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=create_refresh_token(user),
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=not settings.debug,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )
    return Token(access_token=create_access_token(user))


@router.post(
    "/token",
    response_model=Token,
    summary="Authenticate with username/password and issue an access token plus refresh cookie",
    responses={
        400: {"description": "Account deactivated"},
        401: {"description": "Invalid credentials"},
    },
)
@limiter.limit("10/minute")
async def login(
    request: Request, response: Response, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBDep
) -> Token:
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
    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    return issue_token_pair(user, response)


_RESET_RESPONSE = {"detail": "Falls ein aktives Konto zu dieser E-Mail-Adresse existiert, wurde ein Reset-Link versendet."}
_RESET_UNAVAILABLE = "Passwort-Reset ist derzeit nicht verfügbar."
_RESET_COOLDOWN = timedelta(minutes=5)


@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED, summary="Request a password reset")
@limiter.limit("3/hour")
async def request_password_reset(request: Request, data: PasswordResetRequest, db: DBDep) -> dict[str, str]:
    if not settings.smtp_enabled or not settings.katalon_base_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_RESET_UNAVAILABLE)

    # Locking the account serializes requests for the same address: the cooldown
    # check and token insert must see one another before either can commit.
    result = await db.execute(
        select(User).where(User.email == str(data.email), User.is_active.is_(True)).with_for_update()
    )
    user = result.scalar_one_or_none()
    if user is None:
        return _RESET_RESPONSE

    request_hash = hashlib.sha256(user.id.bytes).hexdigest()
    latest_result = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.request_hash == request_hash)
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    now = datetime.now(UTC).replace(tzinfo=None)
    if latest is not None and latest.created_at > now - _RESET_COOLDOWN:
        return _RESET_RESPONSE

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    previous_used_at = latest.used_at if latest is not None else None
    if latest is not None:
        latest.used_at = now
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        delivery_token=encrypt_value(token),
        request_hash=request_hash,
        expires_at=now + timedelta(minutes=30),
    )
    db.add(reset_token)
    await db.commit()
    if enqueue(send_password_reset_email, str(reset_token.id)) is None:
        # The public response remains generic, but a broker outage must not leave
        # an unusable link or a five-minute cooldown behind.
        await db.delete(reset_token)
        if latest is not None:
            latest.used_at = previous_used_at
        await db.commit()
    return _RESET_RESPONSE


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT, summary="Set a new password from a reset token")
@limiter.limit("10/hour")
async def confirm_password_reset(request: Request, data: PasswordResetConfirm, db: DBDep) -> None:
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    result = await db.execute(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(UTC).replace(tzinfo=None),
        )
        .with_for_update()
    )
    reset_token = result.scalar_one_or_none()
    if reset_token is None:
        raise HTTPException(status_code=400, detail="Ungültiger oder abgelaufener Reset-Link")
    user_result = await db.execute(select(User).where(User.id == reset_token.user_id, User.is_active.is_(True)))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Ungültiger oder abgelaufener Reset-Link")
    user.hashed_password = hash_password(data.new_password)
    user.token_version = (user.token_version or 0) + 1
    reset_token.used_at = datetime.now(UTC).replace(tzinfo=None)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Exchange the refresh cookie for a new access token and refresh cookie",
    responses={
        401: {"description": "Invalid or expired refresh token"},
    },
)
@limiter.limit("20/minute")
async def refresh_token(request: Request, response: Response, db: DBDep) -> Token:
    try:
        refresh_token = request.cookies.get(REFRESH_COOKIE)
        if not refresh_token:
            raise ValueError
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("typ")
        token_version = payload.get("ver", 0)
        if user_id_str is None or token_type != "refresh" or not isinstance(token_version, int):
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
    if user is None or not user.is_active or token_version != (user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger Refresh-Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return issue_token_pair(user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Clear the refresh cookie")
async def logout(response: Response) -> Response:
    response.delete_cookie(key=REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True, samesite="strict")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
