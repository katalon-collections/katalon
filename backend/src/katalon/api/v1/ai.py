# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from katalon.core.dependencies import CurrentUser, DBDep, require_admin_or_editor
from katalon.services.ai_service import complete_field

router = APIRouter(prefix="/ai", tags=["ai"])


class AICompleteRequest(BaseModel):
    field_definition_id: uuid.UUID
    record_type: str
    record_id: uuid.UUID
    group_index: int | None = Field(default=None, ge=0)
    group_instance: dict[str, object] | None = None


class AICompleteResponse(BaseModel):
    field_name: str
    value: object
    confidence: float | None = None
    warning: str | None = None
    usage: dict[str, int]


@router.post(
    "/complete",
    response_model=AICompleteResponse,
    dependencies=[require_admin_or_editor()],
    summary="Generate an AI-assisted field completion suggestion",
    responses={
        401: {"description": "Missing, invalid, or expired credentials"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Record or field definition not found"},
        409: {"description": "AI assistance disabled or not fully configured"},
        422: {"description": "Invalid record/field type or malformed AI response"},
        429: {"description": "AI token usage limit exceeded"},
        500: {"description": "Admin configuration missing"},
        502: {"description": "AI provider request failed"},
    },
)
async def complete_ai_field(
    data: AICompleteRequest,
    db: DBDep,
    current_user: CurrentUser,
) -> AICompleteResponse:
    result = await complete_field(
        db,
        user_id=current_user.id,
        record_type=data.record_type,
        record_id=data.record_id,
        field_definition_id=data.field_definition_id,
        group_index=data.group_index,
        group_instance=data.group_instance,
    )
    return AICompleteResponse.model_validate(result)
