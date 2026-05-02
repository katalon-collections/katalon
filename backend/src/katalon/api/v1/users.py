import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from katalon.api.v1.auth import hash_password, verify_password
from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import User
from katalon.core.schemas import PasswordChange, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

_VALID_ROLES = {"admin", "editor", "viewer"}


@router.get("", response_model=list[UserRead], dependencies=[require_role("admin")])
async def list_users(db: DBDep) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


@router.post("", response_model=UserRead, status_code=201, dependencies=[require_role("admin")])
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


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser) -> User:
    return current_user


@router.put("/me/password", status_code=204)
async def change_own_password(data: PasswordChange, db: DBDep, current_user: CurrentUser) -> None:
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Aktuelles Passwort falsch")
    current_user.hashed_password = hash_password(data.new_password)


@router.get("/{user_id}", response_model=UserRead, dependencies=[require_role("admin")])
async def get_user(user_id: uuid.UUID, db: DBDep) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return user


@router.put("/{user_id}", response_model=UserRead, dependencies=[require_role("admin")])
async def update_user(user_id: uuid.UUID, data: UserUpdate, db: DBDep) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if data.role is not None:
        if data.role not in _VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"Ungültige Rolle. Erlaubt: {_VALID_ROLES}")
        user.role = data.role
    if data.email is not None:
        existing = await db.execute(select(User).where(User.email == data.email, User.id != user_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="E-Mail bereits vergeben")
        user.email = data.email
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password is not None:
        user.hashed_password = hash_password(data.password)
    return user


@router.delete("/{user_id}", status_code=204, dependencies=[require_role("admin")])
async def delete_user(user_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> None:
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Eigenes Konto kann nicht gelöscht werden")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    await db.delete(user)
