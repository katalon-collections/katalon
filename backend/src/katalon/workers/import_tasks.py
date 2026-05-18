from __future__ import annotations

import asyncio
from typing import Any

from katalon.workers.celery_app import celery_app


def _run(coro: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="katalon.import_records", bind=True)
def import_records_task(
    self,
    record_type: str,
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    idno_strategy: str = "auto",  # "auto" | "column" | "skip"
    upsert_strategy: str = "skip",  # "skip" | "merge" | "replace"
    user_id: str | None = None,
) -> dict[str, Any]:
    """Import records from CSV/Excel with validation, audit logging, and ES indexing.

    Args:
        record_type: object | entity | place | occurrence
        rows: list of CSV row dicts
        mapping: {csv_column -> field_name}
        idno_strategy: how to handle idno — "auto" generates one, "column" reads from
                       mapped "idno" column, "skip" leaves it null
        upsert_strategy: how to handle existing records by idno — "skip" ignores duplicates,
                         "merge" adds new fields only, "replace" overwrites completely
        user_id: optional UUID of the user who triggered the import (for audit log)
    """
    from katalon.services.importer_service import apply_mapping
    from katalon.database import AsyncSessionLocal
    from katalon.core.models import Object, Entity, Place, Occurrence, AuditLog
    from katalon.services.schema_service import validate_metadata
    from katalon.services.search_service import index_record
    from katalon.services.idno_service import consume_next_idno
    from katalon.services.audit_service import log_change
    from sqlalchemy import select
    from katalon.core.models import AdminConfig

    model_map = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
    }
    model = model_map.get(record_type)
    if model is None:
        return {"error": f"Unknown record_type: {record_type}"}

    # Subtype field name varies by type
    subtype_field = {
        "object": "object_type",
        "entity": "entity_type",
        "place": "place_type",
        "occurrence": "occurrence_type",
    }.get(record_type)

    records, idnos = apply_mapping(rows, mapping)
    created = 0
    updated = 0
    skipped = 0
    errors: list[dict] = []

    # Check if idno is mapped via __idno__
    has_idno_column = "__idno__" in mapping.values()

    async def _import() -> dict[str, Any]:
        nonlocal created, updated, skipped
        async with AsyncSessionLocal() as session:
            # Load idno schema once
            cfg_result = await session.execute(select(AdminConfig).where(AdminConfig.key == "default"))
            cfg = cfg_result.scalar_one_or_none()
            idno_schema = (cfg.idno_schemas or {}).get(record_type) if cfg else None

            # Build lookup of existing records by idno for upsert
            existing_by_idno: dict[str, Any] = {}
            if upsert_strategy != "skip":
                idnos_to_lookup = []
                for i, row_idno in enumerate(idnos):
                    if row_idno:
                        idnos_to_lookup.append(row_idno)
                if idnos_to_lookup:
                    result = await session.execute(select(model).where(model.idno.in_(idnos_to_lookup)))
                    for rec in result.scalars().all():
                        if rec.idno:
                            existing_by_idno[rec.idno] = rec

            total = len(records)
            for i, metadata in enumerate(records):
                row_num = i + 1
                try:
                    self.update_state(
                        state="STARTED",
                        meta={"current": i + 1, "total": total, "stage": "importing"},
                    )
                except Exception:
                    pass

                # Determine idno
                row_idno = idnos[i] if i < len(idnos) else None
                idno: str | None = None
                if has_idno_column and row_idno:
                    idno = row_idno
                elif idno_strategy == "auto" and idno_schema:
                    idno = await consume_next_idno(session, record_type, idno_schema)

                # Handle upsert
                existing = existing_by_idno.get(idno) if idno else None
                if existing:
                    if upsert_strategy == "skip":
                        skipped += 1
                        continue
                    elif upsert_strategy == "merge":
                        # Merge metadata: add new keys, keep existing ones
                        old_meta = existing.metadata_ or {}
                        merged = {**old_meta}
                        for k, v in metadata.items():
                            if k not in merged:
                                merged[k] = v
                        existing.metadata_ = merged
                        updated += 1
                    elif upsert_strategy == "replace":
                        existing.metadata_ = metadata
                        if subtype_field:
                            setattr(existing, subtype_field, None)
                        updated += 1
                    # Index updated record
                    try:
                        await index_record(record_type, existing, session)
                    except Exception:
                        pass
                    continue

                # Validate metadata before insert
                val_errors = await validate_metadata(session, record_type, metadata)
                if val_errors:
                    errors.append({"row": row_num, "error": "; ".join(val_errors)})
                    continue

                # Build kwargs for model
                kwargs: dict[str, Any] = {
                    "metadata_": metadata,
                    "status": "draft",
                }
                if idno:
                    kwargs["idno"] = idno
                if subtype_field:
                    kwargs[subtype_field] = None

                rec = model(**kwargs)
                session.add(rec)
                await session.flush()
                created += 1

                # Audit log per record (fire-and-forget within same session)
                try:
                    await log_change(
                        session,
                        record_type=record_type,
                        record_id=rec.id,
                        user_id=__import__("uuid").UUID(user_id) if user_id else None,
                        action="create",
                        changed_fields={"source": "import", "row": row_num},
                    )
                except Exception:
                    pass

                # Index in Elasticsearch
                try:
                    await index_record(record_type, rec, session)
                except Exception:
                    pass

            await session.commit()

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
        }

    return _run(_import())
