from __future__ import annotations

import logging
import uuid
from typing import Any, cast

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.concurrency import flush_record
from katalon.core.models import Entity, FieldDefinition, Object, Occurrence, Place, Procedure
from katalon.integrations.ark_adapter import ArkAdapter, ArkAdapterError, ark_resolver_link
from katalon.integrations.dnb_urn_adapter import DnbUrnAdapter, DnbUrnAdapterError

logger = logging.getLogger(__name__)

RecordModel = Object | Entity | Place | Occurrence | Procedure

_MODEL_BY_TYPE: dict[str, type[RecordModel]] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "procedure": Procedure,
}

#: PID-Provider, die ein Feld über ``settings.pid_provider`` wählen kann.
PID_PROVIDERS = ("dnb_urn", "ark")
DEFAULT_PID_PROVIDER = "dnb_urn"

#: Portal-Pfade je Datensatztyp ( öffentliche Detail-URL eines Datensatzes ).
_PORTAL_PATHS = {
    "object": "objects",
    "entity": "entities",
    "place": "places",
    "occurrence": "occurrences",
    "procedure": "procedures",
}

#: Tabellen, die bei der ARK-Kollisionsprüfung gelesen werden.
_PID_TABLES = ("objects", "entities", "places", "occurrences", "procedures")


class PidMintError(Exception):
    """PID-Minting ist fehlgeschlagen (Konfiguration oder Provider-Fehler)."""


def record_portal_url(record_type: str, record_id: uuid.UUID) -> str:
    base = settings.katalon_base_url.rstrip("/")
    if not base:
        raise PidMintError(
            "KATALON_BASE_URL ist nicht konfiguriert – die Ziel-URL des Datensatzes "
            "ist für die PID-Vergabe unbekannt."
        )
    return f"{base}/{_PORTAL_PATHS.get(record_type, record_type)}/{record_id}"


def _urn_resolver_link(urn: str) -> str:
    return f"{settings.dnb_urn_resolver_url.rstrip('/')}/{urn}"


def _is_empty_pid_value(value: Any) -> bool:
    return value is None or value == "" or value == []


async def _ark_already_used(db: AsyncSession, ark: str) -> bool:
    """Check whether an ARK value already exists in any record's metadata."""
    jsonpath = f'$.*.value == "{ark}"'
    for table in _PID_TABLES:
        result = await db.execute(
            text(f"SELECT 1 FROM {table} WHERE jsonb_path_exists(metadata_, CAST(:p AS jsonpath)) LIMIT 1"),  # noqa: S608
            {"p": jsonpath},
        )
        if result.first() is not None:
            return True
    return False


async def _mint_ark_unique(db: AsyncSession) -> str:
    adapter = ArkAdapter()
    for _ in range(5):
        try:
            ark = adapter.mint()
        except ArkAdapterError as exc:
            raise PidMintError(str(exc)) from exc
        if not await _ark_already_used(db, ark):
            return ark
    raise PidMintError(
        "ARK-Vergabe fehlgeschlagen: alle generierten Kandidaten existieren bereits."
    )


async def _mint_with_provider(
    db: AsyncSession, provider: str, target_url: str
) -> tuple[str, str]:
    """Mint one PID via the configured provider. Returns (pid, resolver_url)."""
    if provider == "ark":
        ark = await _mint_ark_unique(db)
        return ark, ark_resolver_link(ark)
    if provider == "dnb_urn":
        adapter = DnbUrnAdapter()
        try:
            urn = await adapter.mint_and_register(target_url=target_url)
        except DnbUrnAdapterError as exc:
            raise PidMintError(str(exc)) from exc
        return urn, _urn_resolver_link(urn)
    raise PidMintError(f"Unbekannter PID-Provider '{provider}'.")


def _provider_for_field(field: FieldDefinition) -> str:
    provider = (field.settings or {}).get("pid_provider") or DEFAULT_PID_PROVIDER
    if provider not in PID_PROVIDERS:
        raise PidMintError(
            f"Feld '{field.name}': unbekannter PID-Provider '{provider}' "
            f"(erlaubt: {', '.join(PID_PROVIDERS)})."
        )
    return provider


async def mint_pid_for_record(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID,
    field_name: str,
    target_url: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Mint a PID for a record's pid field and store it in the record metadata.

    The provider is chosen by the field definition's ``settings.pid_provider``.
    """
    model = _MODEL_BY_TYPE.get(record_type)
    if model is None:
        raise ValueError("Ungültiger record_type.")

    record_result = await db.execute(select(model).where(model.id == record_id))
    record = cast(RecordModel | None, record_result.scalar_one_or_none())
    if record is None:
        raise LookupError("Datensatz nicht gefunden.")

    field_result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == record_type,
            FieldDefinition.name == field_name,
            FieldDefinition.field_type == "pid",
            FieldDefinition.is_deleted.is_(False),
        )
    )
    field = field_result.scalar_one_or_none()
    if field is None:
        raise LookupError("PID-Feld nicht gefunden.")

    if not field.is_repeatable and not _is_empty_pid_value((record.metadata_ or {}).get(field_name)):
        raise ValueError("PID-Feld ist bereits reserviert.")

    provider = _provider_for_field(field)
    if target_url is None:
        target_url = record_portal_url(record_type, record_id)
    if label is None:
        label = "ARK" if provider == "ark" else "URN"

    pid, resolver_url = await _mint_with_provider(db, provider, target_url)
    value = {"value": pid, "label": label}

    metadata = dict(record.metadata_ or {})
    if field.is_repeatable:
        existing = metadata.get(field_name)
        entries = list(existing) if isinstance(existing, list) else []
        if not any(isinstance(item, dict) and item.get("value") == pid for item in entries):
            entries.append(value)
        metadata[field_name] = entries
    else:
        metadata[field_name] = value
    record.metadata_ = metadata
    await flush_record(db, record)

    return {
        "pid": pid,
        "resolver_url": resolver_url,
        "value": value,
        "metadata": metadata,
        "provider": provider,
    }


async def register_dnb_urn_for_record(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID,
    field_name: str,
    target_url: str,
    label: str = "URN",
) -> dict[str, Any]:
    """Backwards-compatible wrapper: mint via the field's configured provider."""
    result = await mint_pid_for_record(
        db=db,
        record_type=record_type,
        record_id=record_id,
        field_name=field_name,
        target_url=target_url,
        label=label,
    )
    return {**result, "urn": result["pid"], "resolver_url": result["resolver_url"]}


def _subtype_of(record: Any, record_type: str) -> str | None:
    if record_type == "object":
        return getattr(record, "object_type", None)
    if record_type == "entity":
        return getattr(record, "entity_type", None)
    if record_type == "place":
        return getattr(record, "place_type", None)
    if record_type == "occurrence":
        return getattr(record, "occurrence_type", None)
    return None


async def ensure_pids_on_publish(
    db: AsyncSession,
    record_type: str,
    record: Any,
    user_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Auto-mint missing PIDs when a record becomes publicly visible.

    For every active pid field of the record's type/subtype with a configured
    provider and no value yet, one PID is minted. Raises ``PidMintError`` on
    failure so callers can block the publish instead of silently publishing
    without a PID. Returns the list of mint results (empty if nothing to do).
    """
    from katalon.services.audit_service import log_change
    from katalon.services.schema_service import get_field_definitions

    subtype = _subtype_of(record, record_type)
    fields = await get_field_definitions(db, record_type, subtype)
    minted: list[dict[str, Any]] = []

    for field in fields:
        if field.field_type != "pid":
            continue
        # Auto-mint only runs for fields with an explicitly configured provider —
        # no silent fallback to the (external) DNB default.
        if not (field.settings or {}).get("pid_provider"):
            logger.debug("pid field %s has no pid_provider, skipping auto-mint", field.name)
            continue
        try:
            _provider_for_field(field)
        except PidMintError:
            logger.warning("pid field %s has an invalid pid_provider, skipping auto-mint", field.name)
            continue
        if not _is_empty_pid_value((record.metadata_ or {}).get(field.name)):
            continue
        result = await mint_pid_for_record(
            db=db,
            record_type=record_type,
            record_id=record.id,
            field_name=field.name,
        )
        minted.append(result)
        try:
            await log_change(
                db,
                record_type=record_type,
                record_id=record.id,
                user_id=user_id,
                action="update",
                changed_fields={"pid_field": field.name, "new_value": result["value"]},
            )
        except Exception:
            logger.warning("PID auto-mint audit log failed", exc_info=True)
    return minted


async def count_pid_fields_for_type(db: AsyncSession, record_type: str) -> int:
    result = await db.execute(
        select(func.count()).select_from(FieldDefinition).where(
            FieldDefinition.target_type == record_type,
            FieldDefinition.field_type == "pid",
            FieldDefinition.is_deleted.is_(False),
        )
    )
    return int(result.scalar_one())
