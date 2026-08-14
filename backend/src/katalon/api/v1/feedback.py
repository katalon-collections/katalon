import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from katalon.config import settings
from katalon.core.dependencies import CurrentUser

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackPayload(BaseModel):
    message: str
    url: str
    user: str
    viewport: str
    time: str


async def _deliver(payload: FeedbackPayload) -> None:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise HTTPException(status_code=503, detail="Feedback not configured")

    text = (
        f"📋 *Katalon Feedback*\n\n"
        f"{payload.message}\n\n"
        f"👤 {payload.user}\n"
        f"🔗 {payload.url}\n"
        f"🖥 {payload.viewport}\n"
        f"🕐 {payload.time}"
    )

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": settings.telegram_chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Telegram delivery failed")


@router.post(
    "",
    status_code=204,
    summary="Send in-app feedback message to Telegram (authenticated)",
    responses={
        401: {"description": "Missing, invalid, or expired credentials"},
        502: {"description": "Telegram delivery failed"},
        503: {"description": "Feedback not configured"},
    },
)
async def send_feedback(payload: FeedbackPayload, current_user: CurrentUser) -> None:
    await _deliver(payload)
