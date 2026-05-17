from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import AdminConfig

router = APIRouter(prefix="/admin/config", tags=["admin"])


class AdminConfigRead(BaseModel):
    idno_schemas: dict[str, str]
    idno_patterns: dict[str, str]

    class Config:
        from_attributes = True


class AdminConfigUpdate(BaseModel):
    idno_schemas: dict[str, str] | None = None
    idno_patterns: dict[str, str] | None = None


async def _get_or_create(db: DBDep) -> AdminConfig:
    result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    config = result.scalar_one_or_none()
    if config is None:
        config = AdminConfig(key="default", idno_schemas={}, idno_patterns={})
        db.add(config)
        await db.flush()
    return config


@router.get("", response_model=AdminConfigRead)
async def get_admin_config(db: DBDep, _=require_role("admin")) -> AdminConfig:
    return await _get_or_create(db)


@router.put("", response_model=AdminConfigRead)
async def update_admin_config(
    data: AdminConfigUpdate, db: DBDep, _=require_role("admin")
) -> AdminConfig:
    config = await _get_or_create(db)
    if data.idno_schemas is not None:
        config.idno_schemas = data.idno_schemas
    if data.idno_patterns is not None:
        config.idno_patterns = data.idno_patterns
    await db.flush()
    return config
