from __future__ import annotations

import asyncio
import uuid
from typing import Any

from katalon.workers.celery_app import celery_app


@celery_app.task(name="katalon.import_records", bind=True)
def import_records_task(
    self,
    record_type: str,
    rows: list[dict[str, str]],
    mapping: dict[str, str] | dict[str, Any],
    idno_strategy: str = "auto",  # "auto" | "column" | "skip"
    upsert_strategy: str = "skip",  # "skip" | "merge" | "replace"
    auto_publish: bool = False,
    user_id: str | None = None,
    subtype: str | None = None,
    fields_to_create: list[dict] | None = None,
) -> dict[str, Any]:
    """Import records from CSV/Excel with validation, audit logging, and ES indexing.

    Args:
        record_type: object | entity | place | occurrence
        rows: list of CSV row dicts
        mapping: {csv_column -> field_name} or {csv_column -> {"target": field_name, "delimiter": "..."}}
        idno_strategy: how to handle idno — "auto" generates one, "column" reads from
                       mapped "idno" column, "skip" leaves it null
        upsert_strategy: how to handle existing records by idno — "skip" ignores duplicates,
                         "merge" adds new fields only, "replace" overwrites completely
        auto_publish: if True, attempt to publish each record after creation
        user_id: optional UUID of the user who triggered the import (for audit log)
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm.exc import StaleDataError
    from sqlalchemy.pool import NullPool

    from katalon.config import settings
    from katalon.core.models import (
        AdminConfig,
        Entity,
        FieldDefinition,
        Object,
        Occurrence,
        Place,
        Vocabulary,
        VocabularyTerm,
    )
    from katalon.services.audit_service import log_change
    from katalon.services.idno_service import consume_next_idno
    from katalon.services.importer_service import apply_mapping
    from katalon.services.publish_service import publish_record
    from katalon.services.schema_service import validate_metadata
    from katalon.services.search_service import index_record
    from katalon.services.subtype_service import ensure_subtype_exists

    # NullPool avoids binding connections to a previous event loop across Celery task invocations
    _engine = create_async_engine(settings.database_url, poolclass=NullPool)
    AsyncSessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

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

    # Check if idno is mapped via __idno__
    _mapping_targets = []
    for v in mapping.values():
        if isinstance(v, dict):
            _mapping_targets.append(v.get("target", ""))
        else:
            _mapping_targets.append(v)
    has_idno_column = "__idno__" in _mapping_targets

    import redis as redis_lib

    from katalon.config import settings as _settings
    _redis = redis_lib.from_url(_settings.redis_url, decode_responses=True)

    def _is_cancelled() -> bool:
        return bool(_redis.get(f"cancel:{self.request.id}"))

    created = 0
    updated = 0
    skipped = 0
    published = 0
    publish_failed = 0
    index_failed = 0
    errors: list[dict] = []
    warnings: list[dict] = []
    publish_fail_reasons: list[str] = []  # first few unique reasons

    async def _resolve_vocab_terms(
        session: AsyncSession,
        field_defs: dict[str, Any],
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Replace plain string values in vocab fields with {id, label} dicts.

        Looks up existing terms case-insensitively, creates missing ones, and
        caches per-vocabulary to avoid redundant DB queries.
        """
        # Find all vocab fields that have a vocabulary_id configured
        vocab_fields: dict[str, uuid.UUID] = {}
        for fname, fd in field_defs.items():
            if fd.field_type == "vocab":
                vid = (fd.settings or {}).get("vocabulary_id")
                if vid:
                    try:
                        vocab_fields[fname] = uuid.UUID(str(vid))
                    except ValueError:
                        pass

        if not vocab_fields:
            return records

        # Per-vocabulary term cache: vocab_id -> {lower_term -> {id, label}}
        term_cache: dict[uuid.UUID, dict[str, dict]] = {}

        async def get_term(vocab_id: uuid.UUID, term_str: str) -> dict | None:
            if vocab_id not in term_cache:
                res = await session.execute(
                    select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab_id)
                )
                term_cache[vocab_id] = {
                    t.term.strip().lower(): {"id": str(t.id), "label": t.term}
                    for t in res.scalars().all()
                }
            key = term_str.strip().lower()
            if key in term_cache[vocab_id]:
                return term_cache[vocab_id][key]
            # Term does not exist — check the vocabulary exists before creating
            vocab_res = await session.execute(select(Vocabulary).where(Vocabulary.id == vocab_id))
            if vocab_res.scalar_one_or_none() is None:
                return None
            new_term = VocabularyTerm(
                vocabulary_id=vocab_id,
                term=term_str.strip(),
                label={"de": term_str.strip()},
            )
            session.add(new_term)
            await session.flush()
            entry = {"id": str(new_term.id), "label": new_term.term}
            term_cache[vocab_id][key] = entry
            return entry

        for record in records:
            for fname, vocab_id in vocab_fields.items():
                val = record.get(fname)
                if val is None:
                    continue
                if isinstance(val, list):
                    resolved = []
                    for item in val:
                        if isinstance(item, str) and item.strip():
                            entry = await get_term(vocab_id, item)
                            if entry:
                                resolved.append(entry)
                    if resolved:
                        record[fname] = resolved
                    else:
                        record.pop(fname, None)
                elif isinstance(val, str) and val.strip():
                    entry = await get_term(vocab_id, val)
                    if entry:
                        record[fname] = entry
                    else:
                        record.pop(fname, None)

        return records

    async def _import() -> dict[str, Any]:
        nonlocal created, updated, skipped, published, publish_failed, index_failed, publish_fail_reasons

        async with AsyncSessionLocal() as session:
            # Validate subtype before processing any rows
            await ensure_subtype_exists(session, record_type, subtype)

            # Create field definitions requested alongside this import
            if fields_to_create:
                for f in fields_to_create:
                    name = (f.get("name") or "").strip()
                    if not name:
                        continue
                    existing_fd = (await session.execute(
                        select(FieldDefinition).where(
                            FieldDefinition.target_type == record_type,
                            FieldDefinition.name == name,
                        )
                    )).scalar_one_or_none()
                    if existing_fd:
                        if existing_fd.is_deleted:
                            existing_fd.is_deleted = False
                            existing_fd.field_type = f.get("field_type", "text")
                            existing_fd.is_repeatable = bool(f.get("is_repeatable", False))
                        continue
                    label: dict[str, str] = {}
                    if f.get("label_de"):
                        label["de"] = f["label_de"].strip()
                    if f.get("label_en"):
                        label["en"] = f["label_en"].strip()
                    session.add(FieldDefinition(
                        target_type=record_type,
                        name=name,
                        label=label,
                        field_type=f.get("field_type", "text"),
                        is_required=False,
                        is_repeatable=bool(f.get("is_repeatable", False)),
                        sort_order=0,
                    ))
                await session.flush()

            # Load field_defs once for type conversion in apply_mapping
            fd_result = await session.execute(
                select(FieldDefinition).where(
                    FieldDefinition.target_type == record_type,
                    FieldDefinition.is_deleted.is_(False),
                )
            )
            field_defs = {f.name: f for f in fd_result.scalars().all()}

            records, idnos = apply_mapping(rows, mapping, field_defs)

            # Resolve vocab field values: string → {id, label} by looking up/creating terms
            records = await _resolve_vocab_terms(session, field_defs, records)

            # Load idno schema once
            cfg_result = await session.execute(select(AdminConfig).where(AdminConfig.key == "default"))
            cfg = cfg_result.scalar_one_or_none()
            idno_schema = (cfg.idno_schemas or {}).get(record_type) if cfg else None

            # Build lookup of existing records by idno for upsert
            existing_by_idno: dict[str, Any] = {}
            if upsert_strategy != "skip":
                idnos_to_lookup = [row_idno for row_idno in idnos if row_idno]
                if idnos_to_lookup:
                    result = await session.execute(select(model).where(model.idno.in_(idnos_to_lookup)))
                    for rec in result.scalars().all():
                        if rec.idno:
                            existing_by_idno[rec.idno] = rec

            total = len(records)
            user_uuid = uuid.UUID(user_id) if user_id else None

            for i, metadata in enumerate(records):
                row_num = i + 1
                self.update_state(
                    state="STARTED",
                    meta={"current": i + 1, "total": total, "stage": "importing"},
                )
                if i % 10 == 0 and _is_cancelled():
                    warnings.append({"row": None, "warning": "Import wurde abgebrochen."})
                    break

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

                    conflict = False
                    try:
                        async with session.begin_nested():
                            if upsert_strategy == "merge":
                                old_meta = existing.metadata_ or {}
                                merged = {**old_meta}
                                for k, v in metadata.items():
                                    if k not in merged:
                                        merged[k] = v
                                existing.metadata_ = merged
                            elif upsert_strategy == "replace":
                                existing.metadata_ = metadata
                                if subtype_field:
                                    setattr(existing, subtype_field, subtype)
                            await session.flush()
                    except StaleDataError:
                        conflict = True

                    if conflict:
                        skipped += 1
                        warnings.append({
                            "row": row_num,
                            "warning": (
                                "Datensatz wurde zwischenzeitlich geändert "
                                "(Version-Konflikt) – Zeile übersprungen."
                            ),
                        })
                        continue

                    updated += 1
                    try:
                        await index_record(record_type, existing, session)
                    except Exception as e:
                        index_failed += 1
                        warnings.append({"row": row_num, "warning": f"ES-Indexierung fehlgeschlagen: {e}"})

                    if auto_publish:
                        pub_result = await publish_record(session, record_type, str(existing.id), user_id)
                        if pub_result["ok"]:
                            published += 1
                        else:
                            publish_failed += 1
                            for reason in (pub_result.get("errors") or []):
                                if reason not in publish_fail_reasons and len(publish_fail_reasons) < 5:
                                    publish_fail_reasons.append(reason)
                    continue

                # Validate metadata before insert
                val_errors = await validate_metadata(session, record_type, metadata, subtype, skip_required=True)
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
                    kwargs[subtype_field] = subtype

                rec = model(**kwargs)
                session.add(rec)
                await session.flush()
                created += 1

                try:
                    await log_change(
                        session,
                        record_type=record_type,
                        record_id=rec.id,
                        user_id=user_uuid,
                        action="create",
                        changed_fields={"source": "import", "row": row_num},
                    )
                except Exception as e:
                    warnings.append({"row": row_num, "warning": f"Audit-Log fehlgeschlagen: {e}"})

                try:
                    await index_record(record_type, rec, session)
                except Exception as e:
                    index_failed += 1
                    warnings.append({"row": row_num, "warning": f"ES-Indexierung fehlgeschlagen: {e}"})

                if auto_publish:
                    pub_result = await publish_record(session, record_type, str(rec.id), user_id)
                    if pub_result["ok"]:
                        published += 1
                    else:
                        publish_failed += 1
                        for reason in (pub_result.get("errors") or []):
                            if reason not in publish_fail_reasons and len(publish_fail_reasons) < 5:
                                publish_fail_reasons.append(reason)

            await session.commit()

        # Trigger bulk reindex for this type so all records are consistently indexed
        if created > 0 or updated > 0:
            try:
                from katalon.workers.index_tasks import bulk_reindex_type_task
                bulk_reindex_type_task.delay(record_type)
            except Exception:
                pass  # Celery may not be available

        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "published": published,
            "publish_failed": publish_failed,
            "publish_fail_reasons": publish_fail_reasons,
            "index_failed": index_failed,
            "errors": errors,
            "warnings": warnings,
        }

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_import())
    finally:
        loop.run_until_complete(_engine.dispose())
        loop.close()
