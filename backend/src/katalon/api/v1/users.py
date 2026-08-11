import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from katalon.api.v1.auth import hash_password, verify_password
from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import User
from katalon.core.schemas import (
    EmailChange,
    OnboardingUpdate,
    PasswordChange,
    UserCreate,
    UserRead,
    UserUpdate,
)
from katalon.services.audit_service import log_change

router = APIRouter(prefix="/users", tags=["users"])

_VALID_ROLES = {"admin", "superuser", "editor", "cataloger", "viewer"}


@router.get(
    "",
    response_model=list[UserRead],
    dependencies=[require_role("admin")],
    summary="List all users",
    responses={403: {"description": "Insufficient permissions"}},
)
async def list_users(db: DBDep) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


@router.post(
    "",
    response_model=UserRead,
    status_code=201,
    dependencies=[require_role("admin")],
    summary="Create a new user",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid role"},
        400: {"description": "Email already taken"},
    },
)
async def create_user(data: UserCreate, db: DBDep) -> User:
    if data.role not in _VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Ungültige Rolle. Erlaubt: {_VALID_ROLES}")
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="E-Mail bereits vergeben")
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    return user


@router.get("/me", response_model=UserRead, summary="Get the current authenticated user")
async def get_me(current_user: CurrentUser) -> User:
    return current_user


@router.put(
    "/me/password",
    status_code=204,
    summary="Change the current user's own password",
    responses={400: {"description": "Current password incorrect"}},
)
async def change_own_password(data: PasswordChange, db: DBDep, current_user: CurrentUser) -> None:
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Aktuelles Passwort falsch")
    current_user.hashed_password = hash_password(data.new_password)
    await log_change(
        db,
        record_type="user",
        record_id=current_user.id,
        user_id=current_user.id,
        action="update",
        changed_fields={"password": "updated"},
    )


@router.put(
    "/me/email",
    response_model=UserRead,
    summary="Change the current user's own email",
    responses={400: {"description": "Current password incorrect or email already taken"}},
)
async def change_own_email(data: EmailChange, db: DBDep, current_user: CurrentUser) -> User:
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Aktuelles Passwort falsch")
    existing = await db.execute(
        select(User).where(User.email == data.new_email, User.id != current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="E-Mail bereits vergeben")
    old_email = current_user.email
    current_user.email = str(data.new_email)
    await log_change(
        db,
        record_type="user",
        record_id=current_user.id,
        user_id=current_user.id,
        action="update",
        changed_fields={"email": {"old": old_email, "new": current_user.email}},
    )
    return current_user


@router.put(
    "/me/onboarding",
    response_model=UserRead,
    summary="Mark the current user's onboarding tour as completed or reset it",
)
async def update_own_onboarding(
    data: OnboardingUpdate, db: DBDep, current_user: CurrentUser
) -> User:
    current_user.onboarding_completed_at = (
        datetime.now(UTC).replace(tzinfo=None) if data.completed else None
    )
    await db.flush()
    return current_user


@router.get(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[require_role("admin")],
    summary="Get a user by ID",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "User not found"},
    },
)
async def get_user(user_id: uuid.UUID, db: DBDep) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return user


@router.put(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[require_role("admin")],
    summary="Update a user's role, email, status, or password",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "User not found"},
        422: {"description": "Invalid role"},
        400: {"description": "Invalid self-demotion, self-deactivation, or email already taken"},
    },
)
async def update_user(
    user_id: uuid.UUID, data: UserUpdate, db: DBDep, current_user: CurrentUser
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    changed_fields: dict = {}
    if data.role is not None:
        if data.role not in _VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"Ungültige Rolle. Erlaubt: {_VALID_ROLES}")
        if user_id == current_user.id and user.role == "admin" and data.role != "admin":
            raise HTTPException(
                status_code=400, detail="Eigene Admin-Rolle kann nicht entzogen werden"
            )
        user.role = data.role
        changed_fields["role"] = data.role
    if data.email is not None:
        existing = await db.execute(
            select(User).where(User.email == data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="E-Mail bereits vergeben")
        old_email = user.email
        user.email = data.email
        changed_fields["email"] = {"old": old_email, "new": data.email}
    if data.is_active is not None:
        if user_id == current_user.id and not data.is_active:
            raise HTTPException(
                status_code=400, detail="Eigenes Konto kann nicht deaktiviert werden"
            )
        user.is_active = data.is_active
        changed_fields["is_active"] = data.is_active
    if data.password is not None:
        user.hashed_password = hash_password(data.password)
        changed_fields["password"] = "updated"
    if changed_fields:
        await log_change(
            db,
            record_type="user",
            record_id=user.id,
            user_id=current_user.id,
            action="update",
            changed_fields=changed_fields,
        )
    return user


@router.delete(
    "/{user_id}",
    status_code=204,
    dependencies=[require_role("admin")],
    summary="Delete a user",
    responses={
        403: {"description": "Insufficient permissions"},
        400: {"description": "Cannot delete own account"},
        404: {"description": "User not found"},
    },
)
async def delete_user(user_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> None:
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Eigenes Konto kann nicht gelöscht werden")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    await db.delete(user)
