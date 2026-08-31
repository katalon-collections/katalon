"""SMTP delivery tasks for transactional mail."""

import asyncio
import logging
import smtplib
import ssl
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from katalon.config import settings
from katalon.core.models import PasswordResetToken, User
from katalon.services.secret_service import decrypt_value
from katalon.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _make_session() -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    """Create task-local DB resources; Celery runs each task in a fresh loop."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


def _message(recipient: str, subject: str, text_body: str, html_body: str | None) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return message


def _deliver_email(recipient: str, subject: str, text_body: str, html_body: str | None = None) -> str:
    """Deliver one email. Password-reset tokens never cross the broker boundary."""
    if not settings.smtp_enabled:
        logger.info("SMTP is disabled; skipping email to %s", recipient)
        return "disabled"

    message = _message(recipient, subject, text_body, html_body)
    try:
        connection = (
            smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
                context=ssl.create_default_context(),
            )
            if settings.smtp_ssl_tls
            else smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)
        )
        with connection as client:
            if settings.smtp_starttls:
                client.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
    except Exception:
        logger.warning("SMTP delivery failed for %s", recipient, exc_info=True)
        raise
    return "sent"


@celery_app.task(name="katalon.send_email")
def send_email(recipient: str, subject: str, text_body: str, html_body: str | None = None) -> dict[str, str]:
    """Send one text/plain mail with an optional HTML alternative."""
    return {"status": _deliver_email(recipient, subject, text_body, html_body)}


async def _password_reset_delivery(reset_token_id: str) -> tuple[str, str] | None:
    try:
        reset_id = uuid.UUID(reset_token_id)
    except ValueError:
        logger.warning("Skipping malformed password-reset delivery id")
        return None
    now = datetime.now(UTC).replace(tzinfo=None)
    session_factory, engine = _make_session()
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(PasswordResetToken, User.email)
                .join(User, User.id == PasswordResetToken.user_id)
                .where(
                    PasswordResetToken.id == reset_id,
                    PasswordResetToken.used_at.is_(None),
                    PasswordResetToken.expires_at > now,
                    User.is_active.is_(True),
                )
            )
            row = result.one_or_none()
            if row is None:
                return None
            reset_token, email = row
            return email, decrypt_value(reset_token.delivery_token)
    finally:
        await engine.dispose()


async def _active_user_email(user_id: str) -> str | None:
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        logger.warning("Skipping malformed user email delivery id")
        return None
    session_factory, engine = _make_session()
    try:
        async with session_factory() as db:
            return await db.scalar(
                select(User.email).where(User.id == user_uuid, User.is_active.is_(True))
            )
    finally:
        await engine.dispose()


@celery_app.task(name="katalon.send_user_email")
def send_user_email(user_id: str, subject: str, text_body: str) -> dict[str, str]:
    """Deliver a notification to an active staff user resolved after queuing."""
    recipient = asyncio.run(_active_user_email(user_id))
    if recipient is None:
        return {"status": "skipped"}
    return {"status": _deliver_email(recipient, subject, text_body)}


@celery_app.task(name="katalon.send_password_reset_email")
def send_password_reset_email(reset_token_id: str) -> dict[str, str]:
    """Fetch encrypted reset material after the queue boundary, then deliver it."""
    delivery = asyncio.run(_password_reset_delivery(reset_token_id))
    if delivery is None:
        return {"status": "skipped"}
    recipient, token = delivery
    reset_url = f"{settings.katalon_base_url.rstrip('/')}/admin/#reset-password?token={token}"
    return {
        "status": _deliver_email(
            recipient,
            "Katalon: Passwort zurücksetzen",
            "Setze dein Passwort innerhalb von 30 Minuten zurück:\n\n"
            f"{reset_url}\n\nFalls du das nicht angefordert hast, ignoriere diese E-Mail.",
        )
    }
