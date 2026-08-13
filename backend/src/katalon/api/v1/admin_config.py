import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import AdminConfig, AIUsageEvent, AppSecret
from katalon.services.secret_service import AI_API_KEY_SECRET, delete_secret, set_secret

router = APIRouter(prefix="/admin/config", tags=["admin"])
CHANGELOG_PATHS = (Path("/app/CHANGELOG.md"), Path(__file__).resolve().parents[5] / "CHANGELOG.md")


def _rights_holder_or_none(value: dict | None) -> dict | None:
    if not value:
        return None
    name = str(value.get("name", "")).strip()
    uri = str(value.get("uri", "")).strip()
    if not name:
        return None
    return {"name": name, **({"uri": uri} if uri else {})}


class SecretStatus(BaseModel):
    has_key: bool
    updated_at: datetime | None = None


class AIUsageRead(BaseModel):
    daily_user_tokens: int
    monthly_global_tokens: int


class ChangelogRead(BaseModel):
    content: str


class AdminConfigRead(BaseModel):
    idno_schemas: dict[str, str]
    idno_patterns: dict[str, str]
    reconciliation_enabled: bool
    reconciliation_threshold: int
    reconciliation_id_diff_enabled: bool
    ai_enabled: bool
    ai_base_url: str | None
    ai_model: str | None
    ai_max_input_tokens: int
    ai_max_output_tokens: int
    ai_daily_user_token_limit: int
    ai_monthly_global_token_limit: int
    media_default_license_uri: str | None
    media_default_rights_holder: dict | None
    ai_secret: SecretStatus
    ai_usage: AIUsageRead

    class Config:
        from_attributes = True


class AdminConfigUpdate(BaseModel):
    idno_schemas: dict[str, str] | None = None
    idno_patterns: dict[str, str] | None = None
    reconciliation_enabled: bool | None = None
    reconciliation_threshold: int | None = None
    reconciliation_id_diff_enabled: bool | None = None
    ai_enabled: bool | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    ai_max_input_tokens: int | None = Field(default=None, ge=1, le=128000)
    ai_max_output_tokens: int | None = Field(default=None, ge=1, le=32768)
    ai_daily_user_token_limit: int | None = Field(default=None, ge=1)
    ai_monthly_global_token_limit: int | None = Field(default=None, ge=1)
    media_default_license_uri: str | None = None
    media_default_rights_holder: dict | None = None


async def _get_or_create(db: DBDep) -> AdminConfig:
    result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    config = result.scalar_one_or_none()
    if config is None:
        config = AdminConfig(
            key="default",
            idno_schemas={},
            idno_patterns={},
            ai_base_url="https://api.openai.com/v1",
            ai_model="gpt-4.1-mini",
        )
        db.add(config)
        await db.flush()
    return config


async def _to_read(db: DBDep, config: AdminConfig, user_id: uuid.UUID) -> AdminConfigRead:
    secret_obj = await db.scalar(select(AppSecret).where(AppSecret.key == AI_API_KEY_SECRET))
    now = datetime.now(UTC).replace(tzinfo=None)
    daily_user_tokens = await db.scalar(
        select(func.coalesce(func.sum(AIUsageEvent.input_tokens + AIUsageEvent.output_tokens), 0)).where(
            AIUsageEvent.user_id == user_id,
            AIUsageEvent.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
    ) or 0
    monthly_global_tokens = await db.scalar(
        select(func.coalesce(func.sum(AIUsageEvent.input_tokens + AIUsageEvent.output_tokens), 0)).where(
            AIUsageEvent.created_at >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        )
    ) or 0
    return AdminConfigRead(
        idno_schemas=config.idno_schemas or {},
        idno_patterns=config.idno_patterns or {},
        reconciliation_enabled=config.reconciliation_enabled,
        reconciliation_threshold=config.reconciliation_threshold,
        reconciliation_id_diff_enabled=config.reconciliation_id_diff_enabled,
        ai_enabled=config.ai_enabled,
        ai_base_url=config.ai_base_url,
        ai_model=config.ai_model,
        ai_max_input_tokens=config.ai_max_input_tokens,
        ai_max_output_tokens=config.ai_max_output_tokens,
        ai_daily_user_token_limit=config.ai_daily_user_token_limit,
        ai_monthly_global_token_limit=config.ai_monthly_global_token_limit,
        media_default_license_uri=config.media_default_license_uri,
        media_default_rights_holder=config.media_default_rights_holder,
        ai_secret=SecretStatus(
            has_key=secret_obj is not None,
            updated_at=secret_obj.updated_at if secret_obj is not None else None,
        ),
        ai_usage=AIUsageRead(
            daily_user_tokens=daily_user_tokens,
            monthly_global_tokens=monthly_global_tokens,
        ),
    )


@router.get(
    "",
    response_model=AdminConfigRead,
    summary="Get the admin configuration",
    responses={403: {"description": "Insufficient permissions"}},
)
async def get_admin_config(db: DBDep, current_user = require_role("admin")) -> AdminConfigRead:
    return await _to_read(db, await _get_or_create(db), current_user.id)


@router.get(
    "/changelog",
    response_model=ChangelogRead,
    summary="Get the application changelog",
    responses={403: {"description": "Insufficient permissions"}},
)
async def get_changelog(_=require_role("admin")) -> ChangelogRead:
    for path in CHANGELOG_PATHS:
        try:
            return ChangelogRead(content=path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
    raise HTTPException(status_code=503, detail="Changelog ist nicht verfügbar")


@router.put(
    "",
    response_model=AdminConfigRead,
    summary="Update the admin configuration",
    responses={403: {"description": "Insufficient permissions"}},
)
async def update_admin_config(
    data: AdminConfigUpdate, db: DBDep, current_user = require_role("admin")
) -> AdminConfigRead:
    config = await _get_or_create(db)
    if data.idno_schemas is not None:
        config.idno_schemas = data.idno_schemas
    if data.idno_patterns is not None:
        config.idno_patterns = data.idno_patterns
    if data.reconciliation_enabled is not None:
        config.reconciliation_enabled = data.reconciliation_enabled
    if data.reconciliation_threshold is not None:
        config.reconciliation_threshold = data.reconciliation_threshold
    if data.reconciliation_id_diff_enabled is not None:
        config.reconciliation_id_diff_enabled = data.reconciliation_id_diff_enabled
    if data.ai_enabled is not None:
        config.ai_enabled = data.ai_enabled
    if data.ai_base_url is not None:
        config.ai_base_url = data.ai_base_url.strip() or None
    if data.ai_model is not None:
        config.ai_model = data.ai_model.strip() or None
    if data.ai_max_input_tokens is not None:
        config.ai_max_input_tokens = data.ai_max_input_tokens
    if data.ai_max_output_tokens is not None:
        config.ai_max_output_tokens = data.ai_max_output_tokens
    if data.ai_daily_user_token_limit is not None:
        config.ai_daily_user_token_limit = data.ai_daily_user_token_limit
    if data.ai_monthly_global_token_limit is not None:
        config.ai_monthly_global_token_limit = data.ai_monthly_global_token_limit
    if "media_default_license_uri" in data.model_fields_set:
        config.media_default_license_uri = data.media_default_license_uri.strip() if data.media_default_license_uri else None
    if "media_default_rights_holder" in data.model_fields_set:
        config.media_default_rights_holder = _rights_holder_or_none(data.media_default_rights_holder)
    await db.flush()
    return await _to_read(db, config, current_user.id)


class AdminSecretWrite(BaseModel):
    api_key: str


@router.put(
    "/ai-secret",
    response_model=SecretStatus,
    summary="Set the AI provider API key",
    responses={
        422: {"description": "API key too short"},
        403: {"description": "Insufficient permissions"},
    },
)
async def update_ai_secret(
    data: AdminSecretWrite, db: DBDep, _=require_role("admin")
) -> SecretStatus:
    if len(data.api_key.strip()) < 8:
        raise HTTPException(status_code=422, detail="API-Key ist zu kurz.")
    secret = await set_secret(db, AI_API_KEY_SECRET, data.api_key.strip())
    return SecretStatus(has_key=True, updated_at=secret.updated_at)


@router.delete(
    "/ai-secret",
    response_model=SecretStatus,
    summary="Remove the AI provider API key",
    responses={403: {"description": "Insufficient permissions"}},
)
async def remove_ai_secret(db: DBDep, _=require_role("admin")) -> SecretStatus:
    await delete_secret(db, AI_API_KEY_SECRET)
    return SecretStatus(has_key=False, updated_at=None)
