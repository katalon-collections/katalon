# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import base64
import io
import json
import math
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import httpx
from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.media_storage import storage_path
from katalon.core.models import (
    AdminConfig,
    AIUsageEvent,
    Entity,
    FieldDefinition,
    MediaFile,
    Object,
    Occurrence,
    Place,
    Procedure,
)
from katalon.services.audit_service import log_change
from katalon.services.secret_service import AI_API_KEY_SECRET, get_secret

TEXTISH_FIELD_TYPES = {"text", "richtext", "vocab_free", "date", "number", "boolean"}
AI_IMAGE_MAX_DIMENSION = 1024
MODEL_MAP: dict[str, type[Object] | type[Entity] | type[Place] | type[Occurrence] | type[Procedure]] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "procedure": Procedure,
}


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return text


def _extract_content(message_content: Any) -> str:
    if isinstance(message_content, str):
        return message_content
    if isinstance(message_content, list):
        text_parts: list[str] = []
        for item in message_content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text") or ""))
        return "\n".join(part for part in text_parts if part).strip()
    raise HTTPException(status_code=502, detail="Unerwartetes Antwortformat vom KI-Provider.")


def extract_message_content(data: dict[str, Any]) -> str:
    """Extract the assistant's text content from a chat completion response.

    Reasoning models can exhaust max_tokens on hidden reasoning before ever writing
    to `content`, leaving it null with finish_reason="length" — give a specific,
    actionable error for that case instead of a generic format error.
    """
    choice = data["choices"][0]
    message = choice.get("message") or {}
    content = message.get("content")
    if content is None:
        if choice.get("finish_reason") == "length":
            raise HTTPException(
                status_code=502,
                detail=(
                    "KI-Antwort wurde ohne Inhalt abgeschnitten (Token-Limit erreicht, "
                    "bevor das Modell antworten konnte — z. B. durch Reasoning-Overhead). "
                    "Output-Token-Limit erhöhen oder ein anderes Modell wählen."
                ),
            )
        raise HTTPException(status_code=502, detail="KI-Antwort enthält keinen Inhalt.")
    return _extract_content(content)


def _estimate_tokens(payload: Any) -> int:
    def without_image_data(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: without_image_data(item) for key, item in value.items()}
        if isinstance(value, list):
            return [without_image_data(item) for item in value]
        if isinstance(value, str) and value.startswith("data:image/"):
            return "[image]"
        return value

    return max(1, math.ceil(len(json.dumps(without_image_data(payload), ensure_ascii=False)) / 4))


def _enforce_input_token_limit(estimated_input_tokens: int, limit: int) -> None:
    if estimated_input_tokens > limit:
        raise HTTPException(
            status_code=422,
            detail=f"KI-Anfrage überschreitet das Input-Token-Limit ({limit}).",
        )


async def get_admin_ai_config(db: AsyncSession) -> AdminConfig:
    config = await db.scalar(select(AdminConfig).where(AdminConfig.key == "default"))
    if config is None:
        raise HTTPException(status_code=500, detail="Admin-Konfiguration fehlt.")
    return config


async def ensure_ai_allowed(db: AsyncSession, user_id: uuid.UUID, estimated_input_tokens: int) -> AdminConfig:
    config = await get_admin_ai_config(db)
    if not config.ai_enabled:
        raise HTTPException(status_code=409, detail="KI-Unterstützung ist deaktiviert.")
    if not config.ai_model or not config.ai_base_url:
        raise HTTPException(status_code=409, detail="KI-Anbindung ist nicht vollständig konfiguriert.")
    api_key = await get_secret(db, AI_API_KEY_SECRET)
    if not api_key:
        raise HTTPException(status_code=409, detail="Kein KI-API-Key konfiguriert.")
    _enforce_input_token_limit(estimated_input_tokens, config.ai_max_input_tokens)

    now = datetime.now(UTC).replace(tzinfo=None)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    user_tokens = await db.scalar(
        select(func.coalesce(func.sum(AIUsageEvent.input_tokens + AIUsageEvent.output_tokens), 0)).where(
            AIUsageEvent.user_id == user_id,
            AIUsageEvent.created_at >= start_of_day,
        )
    ) or 0
    if user_tokens + estimated_input_tokens > config.ai_daily_user_token_limit:
        raise HTTPException(status_code=429, detail="Tageslimit für KI-Tokens erreicht.")

    global_tokens = await db.scalar(
        select(func.coalesce(func.sum(AIUsageEvent.input_tokens + AIUsageEvent.output_tokens), 0)).where(
            AIUsageEvent.created_at >= start_of_month,
        )
    ) or 0
    if global_tokens + estimated_input_tokens > config.ai_monthly_global_token_limit:
        raise HTTPException(status_code=429, detail="Monatslimit für KI-Tokens erreicht.")
    return config


async def call_ai_provider(
    config: AdminConfig,
    api_key: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Call the configured OpenAI-compatible chat completion endpoint."""
    assert config.ai_base_url is not None
    payload = {
        "model": config.ai_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    timeout = httpx.Timeout(settings.ai_request_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{config.ai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"KI-Provider-Fehler: {response.text[:400]}")
    result: dict[str, Any] = response.json()
    return result


async def _load_record(db: AsyncSession, record_type: str, record_id: uuid.UUID) -> Any:
    model = MODEL_MAP.get(record_type)
    if model is None:
        raise HTTPException(status_code=422, detail="Unbekannter Datensatztyp.")
    record = await db.scalar(select(model).where(model.id == record_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Datensatz nicht gefunden.")
    return record


async def _load_field(db: AsyncSession, field_definition_id: uuid.UUID) -> FieldDefinition:
    field = await db.scalar(select(FieldDefinition).where(FieldDefinition.id == field_definition_id))
    if field is None or field.is_deleted:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden.")
    return field


async def _load_primary_media(db: AsyncSession, record_type: str, record_id: uuid.UUID) -> MediaFile | None:
    if record_type != "object":
        return None
    return cast(
        MediaFile | None,
        await db.scalar(
            select(MediaFile).where(MediaFile.object_id == record_id, MediaFile.status == "ready").order_by(MediaFile.is_primary.desc(), MediaFile.created_at)
        ),
    )


def _serialize_field_context(field: FieldDefinition, record: Any, include_fields: list[str]) -> dict[str, Any]:
    metadata = getattr(record, "metadata_", {}) or {}
    context: dict[str, Any] = {}
    for name in include_fields:
        if name in metadata:
            context[name] = metadata[name]
    return context


def _prepare_vision_image(media: MediaFile) -> tuple[bytes, str]:
    try:
        with Image.open(storage_path(media.storage_key)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((AI_IMAGE_MAX_DIMENSION, AI_IMAGE_MAX_DIMENSION), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            if "A" in image.getbands() or "transparency" in image.info:
                image.save(output, format="PNG", optimize=True)
                return output.getvalue(), "image/png"
            image.convert("RGB").save(output, format="JPEG", quality=85, optimize=True)
            return output.getvalue(), "image/jpeg"
    except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail="Primärmedium kann nicht für Vision-KI verarbeitet werden.") from exc


def _build_messages(
    field: FieldDefinition,
    record: Any,
    ai_config: dict[str, Any],
    media: MediaFile | None,
    max_output_tokens: int,
    group_instance: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    prompt = str(ai_config.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Für dieses Feld ist kein KI-Prompt konfiguriert.")
    include_fields = [str(name) for name in ai_config.get("include_fields", []) if isinstance(name, str)]
    current_value = (
        group_instance.get(field.name)
        if group_instance is not None
        else (getattr(record, "metadata_", {}) or {}).get(field.name)
    )
    context = {
        "field": {
            "name": field.name,
            "label": field.label,
            "field_type": field.field_type,
            "is_repeatable": field.is_repeatable,
            "settings": field.settings or {},
        },
        "record_type": field.target_type,
        "record_context": _serialize_field_context(field, record, include_fields),
        "current_value": current_value if ai_config.get("send_existing_value") else None,
        "instructions": {
            "output_format": {
                "value": [] if field.is_repeatable else "",
                "confidence": 0.0,
                "warning": "",
            },
            "max_output_tokens": max_output_tokens,
        },
    }
    if group_instance is not None:
        context["group_context"] = {
            name: value for name, value in group_instance.items() if name != field.name
        }
    user_text = (
        f"{prompt}\n\n"
        "Antworte nur mit JSON. Nutze Schema: "
        '{"value": ..., "confidence": 0.0, "warning": ""}. '
        "Kein Markdown, keine Erklärungen."
        f"\n\nKontext:\n{json.dumps(context, ensure_ascii=False)}"
    )
    if ai_config.get("mode") == "vision":
        if media is None:
            raise HTTPException(status_code=422, detail="Für Vision-KI wird ein Primärmedium benötigt.")
        file_bytes, mime_type = _prepare_vision_image(media)
        b64 = base64.b64encode(file_bytes).decode("ascii")
        return [
            {
                "role": "system",
                "content": "Du erzeugst präzise Feldvorschläge für ein Metadatenformular. Erfinde nichts bei Unsicherheit.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ],
            },
        ]
    return [
        {
            "role": "system",
            "content": "Du erzeugst präzise Feldvorschläge für ein Metadatenformular. Erfinde nichts bei Unsicherheit.",
        },
        {"role": "user", "content": user_text},
    ]


def _coerce_value(field: FieldDefinition, value: Any) -> Any:
    if field.is_repeatable:
        if not isinstance(value, list):
            raise HTTPException(status_code=422, detail="KI-Antwort für wiederholbares Feld muss Liste sein.")
        return value
    if field.field_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        raise HTTPException(status_code=422, detail="KI-Antwort für Boolean-Feld ungültig.")
    if field.field_type == "number":
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return float(value) if "." in value else int(value)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="KI-Antwort für Zahlenfeld ungültig.") from exc
    if field.field_type in TEXTISH_FIELD_TYPES:
        if isinstance(value, (str, int, float, bool)):
            return value
    raise HTTPException(status_code=422, detail="KI-Antwort passt nicht zum Feldtyp.")


async def complete_field(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    record_type: str,
    record_id: uuid.UUID,
    field_definition_id: uuid.UUID,
    group_index: int | None = None,
    group_instance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    field = await _load_field(db, field_definition_id)
    if field.target_type != record_type:
        raise HTTPException(status_code=422, detail="Felddefinition passt nicht zum Datensatztyp.")
    if field.field_type not in TEXTISH_FIELD_TYPES:
        raise HTTPException(status_code=422, detail="KI-Vervollständigung ist für diesen Feldtyp nicht aktiviert.")

    ai_config = (field.settings or {}).get("ai_config")
    if not isinstance(ai_config, dict) or not ai_config.get("enabled"):
        raise HTTPException(status_code=422, detail="Für dieses Feld ist keine KI-Konfiguration aktiv.")

    record = await _load_record(db, record_type, record_id)
    if field.parent_id is not None:
        if group_index is None or group_instance is None:
            raise HTTPException(status_code=422, detail="Gruppenindex oder Gruppeninstanz fehlt.")
        parent = await _load_field(db, field.parent_id)
        if parent.field_type != "group" or parent.target_type != record_type:
            raise HTTPException(status_code=422, detail="Ungültiges Gruppen-Subfeld.")
    elif group_index is not None or group_instance is not None:
        raise HTTPException(status_code=422, detail="Gruppenkontext ist nur für Subfelder erlaubt.")
    config = await get_admin_ai_config(db)
    media = await _load_primary_media(db, record_type, record_id)
    messages = _build_messages(
        field,
        record,
        ai_config,
        media,
        config.ai_max_output_tokens,
        group_instance,
    )
    estimated_input_tokens = _estimate_tokens(messages)
    config = await ensure_ai_allowed(db, user_id, estimated_input_tokens)
    api_key = await get_secret(db, AI_API_KEY_SECRET)
    assert api_key is not None

    data = await call_ai_provider(config, api_key, messages, config.ai_max_output_tokens)
    content = extract_message_content(data)
    try:
        parsed = json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="KI-Antwort war kein gültiges JSON.") from exc
    coerced_value = _coerce_value(field, parsed.get("value"))
    usage = data.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or estimated_input_tokens)
    output_tokens = int(usage.get("completion_tokens") or _estimate_tokens(parsed))
    db.add(
        AIUsageEvent(
            user_id=user_id,
            provider="openai-compatible",
            model=str(config.ai_model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    )
    await log_change(
        db,
        record_type=record_type,
        record_id=record_id,
        user_id=user_id,
        action="ai_complete",
        changed_fields={
            "field_definition_id": str(field.id),
            "field_name": field.name,
            "group_index": group_index,
            "provider": "openai-compatible",
            "model": config.ai_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )
    await db.flush()
    return {
        "field_name": field.name,
        "value": coerced_value,
        "confidence": parsed.get("confidence"),
        "warning": parsed.get("warning"),
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }
