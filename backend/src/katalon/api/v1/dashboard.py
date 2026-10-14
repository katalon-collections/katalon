# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from fastapi import APIRouter

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.services.dashboard_service import DashboardSummary, get_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Get operational workspace summary for current user",
)
async def get_summary(db: DBDep, current_user: CurrentUser) -> DashboardSummary:
    return await get_dashboard_summary(db, current_user)
