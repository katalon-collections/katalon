# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.services import pid_service
from katalon.services.audit_service import log_change
from katalon.services.pid_service import PidMintError

router = APIRouter(prefix="/pids", tags=["pids"])
logger = logging.getLogger(__name__)


class PidMintIn(BaseModel):
    record_type: str
    record_id: uuid.UUID
    field_name: str
    target_url: HttpUrl | None = None
    label: str | None = None


class PidMintOut(BaseModel):
    pid: str
    resolver_url: str
    provider: str
    value: dict[str, Any]


async def _mint_and_audit(
    data: PidMintIn, db: Any, current_user: Any, endpoint_label: str
) -> PidMintOut:
    """Shared mint + audit path for /mint and the legacy /urn/register endpoint."""
    try:
        result = await pid_service.mint_pid_for_record(
            db=db,
            record_type=data.record_type,
            record_id=data.record_id,
            field_name=data.field_name,
            target_url=str(data.target_url) if data.target_url else None,
            label=data.label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PidMintError as exc:
        raise HTTPException(status_code=502, detail=f"{endpoint_label} fehlgeschlagen: {exc}")
    except httpx.HTTPStatusError as exc:
        detail = f"PID-Provider-API-Fehler: HTTP {exc.response.status_code}"
        raise HTTPException(status_code=502, detail=detail)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during PID minting")
        raise HTTPException(status_code=500, detail="PID-Vergabe fehlgeschlagen.")

    await log_change(
        db,
        record_type=data.record_type,
        record_id=data.record_id,
        user_id=current_user.id,
        action="update",
        changed_fields={"pid_field": data.field_name, "new_value": result["value"]},
    )
    return PidMintOut(
        pid=result["pid"],
        resolver_url=result["resolver_url"],
        provider=result["provider"],
        value=result["value"],
    )


@router.post(
    "/mint",
    response_model=PidMintOut,
    summary="Mint a persistent identifier for a record's pid field",
    description=(
        "Mints a PID via the provider configured on the pid field "
        "(`settings.pid_provider`: 'dnb_urn' or 'ark'). If `target_url` is omitted, "
        "the server derives it from KATALON_BASE_URL and the record's portal path."
    ),
    responses={
        401: {"description": "Missing, invalid, or expired credentials"},
        404: {"description": "Record or pid field not found"},
        422: {"description": "Invalid input data"},
        502: {"description": "PID provider failed or is misconfigured"},
        500: {"description": "Unexpected error during PID minting"},
    },
)
async def mint_pid(data: PidMintIn, db: DBDep, current_user: CurrentUser) -> PidMintOut:
    return await _mint_and_audit(data, db, current_user, "PID-Vergabe")


@router.post(
    "/urn/register",
    response_model=PidMintOut,
    summary="Register a DNB URN persistent identifier for a record field (legacy)",
    description=(
        "Legacy alias of POST /pids/mint kept for existing clients. The provider "
        "still follows the pid field's `pid_provider` setting."
    ),
    responses={
        401: {"description": "Missing, invalid, or expired credentials"},
        404: {"description": "Record, field, or admin config not found"},
        422: {"description": "Invalid input data"},
        500: {"description": "Unexpected error during URN registration"},
        502: {"description": "DNB URN API request failed"},
    },
)
async def register_dnb_urn(data: PidMintIn, db: DBDep, current_user: CurrentUser) -> PidMintOut:
    return await _mint_and_audit(data, db, current_user, "URN-Registrierung")
