import uuid
from email.message import EmailMessage
from unittest.mock import AsyncMock, MagicMock

from katalon.workers import email_tasks


class _SMTP:
    instances: list["_SMTP"] = []

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.starttls = MagicMock()
        self.login = MagicMock()
        self.send_message = MagicMock()
        self.instances.append(self)

    def __enter__(self) -> "_SMTP":
        return self

    def __exit__(self, *args) -> None:
        return None


def test_send_email_skips_when_smtp_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(email_tasks.settings, "smtp_enabled", False)
    smtp = MagicMock()
    monkeypatch.setattr(email_tasks.smtplib, "SMTP", smtp)

    assert email_tasks.send_email.run("admin@example.org", "Subject", "Text") == {"status": "disabled"}
    smtp.assert_not_called()


def test_send_email_uses_starttls_and_html_alternative(monkeypatch) -> None:
    _SMTP.instances.clear()
    monkeypatch.setattr(email_tasks.settings, "smtp_enabled", True)
    monkeypatch.setattr(email_tasks.settings, "smtp_host", "smtp.example.org")
    monkeypatch.setattr(email_tasks.settings, "smtp_port", 587)
    monkeypatch.setattr(email_tasks.settings, "smtp_timeout_seconds", 12)
    monkeypatch.setattr(email_tasks.settings, "smtp_from", "Katalon <noreply@example.org>")
    monkeypatch.setattr(email_tasks.settings, "smtp_starttls", True)
    monkeypatch.setattr(email_tasks.settings, "smtp_ssl_tls", False)
    monkeypatch.setattr(email_tasks.settings, "smtp_username", "user")
    monkeypatch.setattr(email_tasks.settings, "smtp_password", "secret")
    monkeypatch.setattr(email_tasks.smtplib, "SMTP", _SMTP)

    assert email_tasks.send_email.run("admin@example.org", "Subject", "Text", "<p>Text</p>") == {
        "status": "sent"
    }

    client = _SMTP.instances[0]
    assert client.args == ("smtp.example.org", 587)
    assert client.kwargs == {"timeout": 12}
    client.starttls.assert_called_once()
    client.login.assert_called_once_with("user", "secret")
    message = client.send_message.call_args.args[0]
    assert isinstance(message, EmailMessage)
    assert message["To"] == "admin@example.org"
    assert message.get_body(("html",)).get_content().strip() == "<p>Text</p>"


def test_send_email_uses_a_verifying_context_for_implicit_tls(monkeypatch) -> None:
    _SMTP.instances.clear()
    monkeypatch.setattr(email_tasks.settings, "smtp_enabled", True)
    monkeypatch.setattr(email_tasks.settings, "smtp_host", "smtp.example.org")
    monkeypatch.setattr(email_tasks.settings, "smtp_port", 465)
    monkeypatch.setattr(email_tasks.settings, "smtp_timeout_seconds", 12)
    monkeypatch.setattr(email_tasks.settings, "smtp_from", "Katalon <noreply@example.org>")
    monkeypatch.setattr(email_tasks.settings, "smtp_starttls", False)
    monkeypatch.setattr(email_tasks.settings, "smtp_ssl_tls", True)
    monkeypatch.setattr(email_tasks.settings, "smtp_username", "")
    monkeypatch.setattr(email_tasks.settings, "smtp_password", "")
    monkeypatch.setattr(email_tasks.smtplib, "SMTP_SSL", _SMTP)
    context = object()
    monkeypatch.setattr(email_tasks.ssl, "create_default_context", lambda: context)

    assert email_tasks.send_email.run("admin@example.org", "Subject", "Text") == {"status": "sent"}

    client = _SMTP.instances[0]
    assert client.kwargs == {"timeout": 12, "context": context}
    client.starttls.assert_not_called()


async def test_password_reset_delivery_uses_task_local_nullpool_session(monkeypatch) -> None:
    engine = MagicMock()
    engine.dispose = AsyncMock()
    session = MagicMock()
    result = MagicMock()
    result.one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    session_factory = MagicMock(return_value=session_cm)
    monkeypatch.setattr(email_tasks, "_make_session", lambda: (session_factory, engine))

    assert await email_tasks._password_reset_delivery(str(uuid.uuid4())) is None
    session_factory.assert_called_once()
    engine.dispose.assert_awaited_once()


def test_send_user_email_skips_missing_or_inactive_user(monkeypatch) -> None:
    monkeypatch.setattr(email_tasks, "_active_user_email", AsyncMock(return_value=None))
    deliver = MagicMock()
    monkeypatch.setattr(email_tasks, "_deliver_email", deliver)

    assert email_tasks.send_user_email.run(str(uuid.uuid4()), "Subject", "Text") == {"status": "skipped"}
    deliver.assert_not_called()


def test_send_user_email_resolves_recipient_in_worker(monkeypatch) -> None:
    user_id = str(uuid.uuid4())
    monkeypatch.setattr(email_tasks, "_active_user_email", AsyncMock(return_value="admin@example.org"))
    deliver = MagicMock(return_value="sent")
    monkeypatch.setattr(email_tasks, "_deliver_email", deliver)

    assert email_tasks.send_user_email.run(user_id, "Subject", "Text") == {"status": "sent"}
    deliver.assert_called_once_with("admin@example.org", "Subject", "Text")
