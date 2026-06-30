import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from katalon.core.dependencies import CurrentUser, DBDep, require_admin_or_editor
from katalon.services.ai_service import complete_field

router = APIRouter(prefix="/ai", tags=["ai"])


class AICompleteRequest(BaseModel):
    field_definition_id: uuid.UUID
    record_type: str
    record_id: uuid.UUID


class AICompleteResponse(BaseModel):
    field_name: str
    value: object
    confidence: float | None = None
    warning: str | None = None
    usage: dict[str, int]


@router.post("/complete", response_model=AICompleteResponse, dependencies=[require_admin_or_editor()])
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
    )
    return AICompleteResponse.model_validate(result)
