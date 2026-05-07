from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.services import pid_service
from katalon.services.audit_service import log_change

router = APIRouter(prefix="/pids", tags=["pids"])


class DnbUrnRegisterIn(BaseModel):
    record_type: str
    record_id: uuid.UUID
    field_name: str
    target_url: HttpUrl
    label: str = "URN"


class DnbUrnRegisterOut(BaseModel):
    urn: str
    resolver_url: str
    value: dict


@router.post("/urn/register", response_model=DnbUrnRegisterOut)
async def register_dnb_urn(
    data: DnbUrnRegisterIn, db: DBDep, current_user: CurrentUser
) -> DnbUrnRegisterOut:
    try:
        result = await pid_service.register_dnb_urn_for_record(
            db=db,
            record_type=data.record_type,
            record_id=data.record_id,
            field_name=data.field_name,
            target_url=str(data.target_url),
            label=data.label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        detail = f"DNB-URN-API Fehler: HTTP {exc.response.status_code}"
        raise HTTPException(status_code=502, detail=detail)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await log_change(
        db,
        record_type=data.record_type,
        record_id=data.record_id,
        user_id=current_user.id,
        action="update",
        changed_fields={"pid_field": data.field_name, "new_value": result["value"]},
    )
    return DnbUrnRegisterOut(
        urn=result["urn"],
        resolver_url=result["resolver_url"],
        value=result["value"],
    )
